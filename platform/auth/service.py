"""
Auth service — user registration, login, JWT token management.

Uses bcrypt for password hashing and PyJWT for token generation.
Tokens are stored as httponly cookies (access 15min, refresh 7 days).
"""

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

try:
    import bcrypt
except ImportError:
    bcrypt = None  # type: ignore

try:
    import jwt as pyjwt
except ImportError:
    pyjwt = None  # type: ignore

from ..db.migrations import get_db

# JWT config
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRY = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRY = timedelta(days=7)


def _ensure_jwt_secret() -> str:
    """Return JWT secret, auto-generating one if not set."""
    global JWT_SECRET
    if JWT_SECRET:
        return JWT_SECRET
    # Generate and persist in DB for consistency across restarts
    with get_db() as db:
        row = db.execute(
            "SELECT value FROM session_state WHERE key='jwt_secret'"
        ).fetchone()
        if row:
            JWT_SECRET = row[0] if isinstance(row, tuple) else row["value"]
            return JWT_SECRET
        # First time — generate
        db.execute(
            "CREATE TABLE IF NOT EXISTS session_state (key TEXT PRIMARY KEY, value TEXT)"
        )
        secret = uuid.uuid4().hex + uuid.uuid4().hex
        db.execute(
            "INSERT OR REPLACE INTO session_state (key, value) VALUES ('jwt_secret', ?)",
            (secret,),
        )
        db.commit()
    JWT_SECRET = secret
    return JWT_SECRET


@dataclass
class User:
    id: str
    email: str
    display_name: str
    role: str  # admin, project_manager, developer, viewer
    avatar: str = ""
    is_active: bool = True
    auth_provider: str = "local"
    last_login: Optional[str] = None
    created_at: Optional[str] = None


class AuthError(Exception):
    """Authentication/authorization error."""

    def __init__(self, message: str, code: str = "auth_error"):
        super().__init__(message)
        self.code = code


def _hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    if bcrypt is None:
        # Fallback: SHA256 with salt (less secure, but works without bcrypt)
        salt = os.urandom(16).hex()
        h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return f"sha256:{salt}:{h}"
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    if password_hash.startswith("sha256:"):
        _, salt, h = password_hash.split(":", 2)
        return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == h
    if bcrypt is None:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _ts(v) -> str | None:
    """Normalize a timestamp value to ISO string (handles datetime objects from PG)."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    # datetime / date objects (PostgreSQL psycopg2)
    return v.isoformat()


def _row_to_user(row) -> User:
    """Convert DB row to User object."""
    if isinstance(row, tuple):
        return User(
            id=row[0],
            email=row[1],
            display_name=row[3],
            role=row[4],
            avatar=row[5] or "",
            is_active=bool(row[6]),
            auth_provider=row[7] or "local",
            last_login=_ts(row[9]),
            created_at=_ts(row[10]),
        )
    return User(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"],
        avatar=row["avatar"] or "",
        is_active=bool(row["is_active"]),
        auth_provider=row["auth_provider"] or "local",
        last_login=_ts(row["last_login"]),
        created_at=_ts(row["created_at"]),
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


def user_count() -> int:
    """Return total number of users (for setup wizard check)."""
    try:
        with get_db() as db:
            row = db.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if isinstance(row, tuple) else row[0]
    except Exception:
        return 0


def _ensure_personal_space(user: "User") -> None:
    """Create a personal space project for a new OAuth user (idempotent)."""
    try:
        from ..projects.manager import get_project_store, Project

        store = get_project_store()
        space_id = f"space-{user.id}"
        existing = store.get(space_id)
        if existing:
            return
        p = Project(
            id=space_id,
            name=f"{user.display_name}'s Space",
            description=f"Personal workspace for {user.display_name}",
            factory_type="standalone",
            lead_agent_id="brain",
            owner_id=user.id,
            values=["quality", "feedback"],
        )
        store.create(p)
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("_ensure_personal_space failed: %s", e)


def force_reset_password(email: str, new_password: str) -> None:
    """Force-reset a user's password (used by demo_login when hash is stale)."""
    pw_hash = _hash_password(new_password)
    with get_db() as db:
        db.execute(
            "UPDATE users SET password_hash=? WHERE email=?",
            (pw_hash, email.strip().lower()),
        )
        db.commit()


def register(
    email: str,
    password: str,
    display_name: str,
    role: str = "viewer",
) -> User:
    """Register a new user. Raises AuthError if email already taken."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise AuthError("Invalid email", "invalid_email")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters", "weak_password")

    user_id = uuid.uuid4().hex[:12]
    password_hash = _hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            raise AuthError("Email already registered", "email_taken")
        db.execute(
            "INSERT INTO users (id, email, password_hash, display_name, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, email, password_hash, display_name.strip(), role, now),
        )
        db.commit()

    return User(
        id=user_id,
        email=email,
        display_name=display_name.strip(),
        role=role,
        created_at=now,
    )


def oauth_login_or_create(
    email: str,
    display_name: str,
    auth_provider: str,
    avatar: str = "",
    ip: str = "",
    ua: str = "",
) -> dict:
    """Login or create user from OAuth provider. Returns tokens dict."""
    email = email.strip().lower()
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if row:
            user = _row_to_user(row)
            # Update provider info if needed
            if user.auth_provider != auth_provider:
                db.execute(
                    "UPDATE users SET auth_provider=? WHERE id=?",
                    (auth_provider, user.id),
                )
                db.commit()
        else:
            # Create new user from OAuth
            user_id = uuid.uuid4().hex[:12]
            now = datetime.now(timezone.utc).isoformat()
            # First user = admin, rest = developer
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()
            role = (
                "admin"
                if (count[0] if isinstance(count, tuple) else count["COUNT(*)"]) == 0
                else "developer"
            )
            db.execute(
                "INSERT INTO users (id, email, password_hash, display_name, role, avatar, auth_provider, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    email,
                    "",
                    display_name.strip(),
                    role,
                    avatar,
                    auth_provider,
                    now,
                ),
            )
            db.commit()
            user = User(
                id=user_id,
                email=email,
                display_name=display_name.strip(),
                role=role,
                avatar=avatar,
                auth_provider=auth_provider,
                created_at=now,
            )

        # Update last login
        now_ts = datetime.now(timezone.utc).isoformat()
        db.execute("UPDATE users SET last_login=? WHERE id=?", (now_ts, user.id))
        db.commit()

    # Auto-create personal space on first OAuth login (if not already existing)
    if not row:
        _ensure_personal_space(user)

    access = _create_access_token(user)
    refresh = _create_refresh_token(user, ip=ip, ua=ua)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "avatar": user.avatar,
        },
    }


def get_user_by_id(user_id: str) -> Optional[User]:
    """Get user by ID."""
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
        ).fetchone()
    return _row_to_user(row) if row else None


def list_users() -> list[User]:
    """List all users."""
    with get_db() as db:
        rows = db.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [_row_to_user(r) for r in rows]


def update_user(user_id: str, **kwargs) -> Optional[User]:
    """Update user fields. Allowed: display_name, role, avatar, is_active."""
    allowed = {"display_name", "role", "avatar", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_user_by_id(user_id)

    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [user_id]
    with get_db() as db:
        db.execute(f"UPDATE users SET {sets} WHERE id=?", vals)
        db.commit()
    return get_user_by_id(user_id)


def delete_user(user_id: str) -> bool:
    """Delete user and related data."""
    with get_db() as db:
        db.execute("DELETE FROM user_sessions WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM user_project_roles WHERE user_id=?", (user_id,))
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
        db.commit()
    return True


# ---------------------------------------------------------------------------
# Project roles
# ---------------------------------------------------------------------------


def set_project_role(user_id: str, project_id: str, role: str, granted_by: str = ""):
    """Set user role for a specific project."""
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO user_project_roles (user_id, project_id, role, granted_by) "
            "VALUES (?, ?, ?, ?)",
            (user_id, project_id, role, granted_by),
        )
        db.commit()


def get_project_role(user_id: str, project_id: str) -> str:
    """Get user role for a project. Falls back to global role."""
    with get_db() as db:
        row = db.execute(
            "SELECT role FROM user_project_roles WHERE user_id=? AND project_id=?",
            (user_id, project_id),
        ).fetchone()
    if row:
        return row[0] if isinstance(row, tuple) else row["role"]
    # Fallback: global role
    user = get_user_by_id(user_id)
    return user.role if user else "viewer"


def get_user_projects(user_id: str) -> list[dict]:
    """Get all project roles for a user."""
    try:
        with get_db() as db:
            rows = db.execute(
                "SELECT project_id, role FROM user_project_roles WHERE user_id=?",
                (user_id,),
            ).fetchall()
        return [
            {
                "project_id": r[0] if isinstance(r, tuple) else r["project_id"],
                "role": r[1] if isinstance(r, tuple) else r["role"],
            }
            for r in rows
        ]
    except Exception:
        return []


def remove_project_role(user_id: str, project_id: str):
    """Remove user role for a project (falls back to global role)."""
    with get_db() as db:
        db.execute(
            "DELETE FROM user_project_roles WHERE user_id=? AND project_id=?",
            (user_id, project_id),
        )
        db.commit()


# ---------------------------------------------------------------------------
# JWT Token management
# ---------------------------------------------------------------------------


def _create_access_token(user: User) -> str:
    """Create JWT access token (short-lived)."""
    secret = _ensure_jwt_secret()
    if pyjwt is None:
        raise AuthError("PyJWT not installed", "missing_dependency")
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "name": user.display_name,
        "type": "access",
        "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_EXPIRY,
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _create_refresh_token(user: User, ip: str = "", ua: str = "") -> str:
    """Create refresh token and store session in DB."""
    secret = _ensure_jwt_secret()
    if pyjwt is None:
        raise AuthError("PyJWT not installed", "missing_dependency")

    session_id = uuid.uuid4().hex[:16]
    expires = datetime.now(timezone.utc) + REFRESH_TOKEN_EXPIRY

    payload = {
        "sub": user.id,
        "sid": session_id,
        "type": "refresh",
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    token = pyjwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with get_db() as db:
        db.execute(
            "INSERT INTO user_sessions (id, user_id, refresh_token_hash, user_agent, ip_address, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, user.id, token_hash, ua[:200], ip[:45], expires.isoformat()),
        )
        db.commit()
    return token


def login(email: str, password: str, ip: str = "", ua: str = "") -> dict:
    """Authenticate user, return access + refresh tokens."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email=? AND is_active=1",
            (email.strip().lower(),),
        ).fetchone()
    if not row:
        raise AuthError("Invalid credentials", "invalid_credentials")

    pw_hash = row[2] if isinstance(row, tuple) else row["password_hash"]
    if not _verify_password(password, pw_hash):
        raise AuthError("Invalid credentials", "invalid_credentials")

    user = _row_to_user(row)

    # Update last_login
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("UPDATE users SET last_login=? WHERE id=?", (now, user.id))
        db.commit()

    access = _create_access_token(user)
    refresh = _create_refresh_token(user, ip=ip, ua=ua)

    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "avatar": user.avatar,
        },
    }


def verify_access_token(token: str) -> Optional[User]:
    """Verify JWT access token, return User or None."""
    secret = _ensure_jwt_secret()
    if pyjwt is None:
        return None
    try:
        payload = pyjwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return get_user_by_id(payload["sub"])
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        return None


def refresh_tokens(refresh_token: str, ip: str = "", ua: str = "") -> dict:
    """Rotate refresh token, return new access + refresh tokens."""
    secret = _ensure_jwt_secret()
    if pyjwt is None:
        raise AuthError("PyJWT not installed", "missing_dependency")

    try:
        payload = pyjwt.decode(refresh_token, secret, algorithms=[JWT_ALGORITHM])
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
        raise AuthError("Invalid refresh token", "invalid_token")

    if payload.get("type") != "refresh":
        raise AuthError("Invalid token type", "invalid_token")

    session_id = payload.get("sid")
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM user_sessions WHERE id=? AND refresh_token_hash=?",
            (session_id, token_hash),
        ).fetchone()
    if not row:
        raise AuthError("Session not found or token already rotated", "invalid_session")

    user = get_user_by_id(payload["sub"])
    if not user or not user.is_active:
        raise AuthError("User not found or inactive", "user_inactive")

    # Rotate: delete old session, create new
    with get_db() as db:
        db.execute("DELETE FROM user_sessions WHERE id=?", (session_id,))
        db.commit()

    access = _create_access_token(user)
    refresh = _create_refresh_token(user, ip=ip, ua=ua)

    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "avatar": user.avatar,
        },
    }


def logout(user_id: str, session_id: str = ""):
    """Logout: invalidate refresh token session(s)."""
    with get_db() as db:
        if session_id:
            db.execute(
                "DELETE FROM user_sessions WHERE id=? AND user_id=?",
                (session_id, user_id),
            )
        else:
            # Logout all sessions
            db.execute("DELETE FROM user_sessions WHERE user_id=?", (user_id,))
        db.commit()


def cleanup_expired_sessions():
    """Remove expired refresh token sessions."""
    with get_db() as db:
        db.execute(
            "DELETE FROM user_sessions WHERE expires_at < ?",
            (datetime.now(timezone.utc).isoformat(),),
        )
        db.commit()


# ---------------------------------------------------------------------------
# Password reset (6-digit code via AWS SES)
# ---------------------------------------------------------------------------

RESET_CODE_EXPIRY = timedelta(minutes=15)
RESET_MAX_ATTEMPTS = 5


def _generate_reset_code() -> str:
    """Generate a cryptographically random 6-digit code."""
    import secrets
    return f"{secrets.randbelow(1_000_000):06d}"


def request_password_reset(email: str) -> bool:
    """Generate reset code, store in DB, send via SES.

    Returns True if email was sent (or user not found — same response to prevent enumeration).
    """
    email = email.strip().lower()
    user = get_user_by_email(email)
    if not user:
        # Don't reveal whether email exists
        return True

    code = _generate_reset_code()
    expires = datetime.now(timezone.utc) + RESET_CODE_EXPIRY

    with get_db() as db:
        # Invalidate previous codes for this email
        db.execute(
            "UPDATE password_reset_codes SET used=1 WHERE email=? AND used=0",
            (email,),
        )
        db.execute(
            "INSERT INTO password_reset_codes (id, email, code_hash, expires_at, attempts, used) "
            "VALUES (?, ?, ?, ?, 0, 0)",
            (
                uuid.uuid4().hex[:16],
                email,
                hashlib.sha256(code.encode()).hexdigest(),
                expires.isoformat(),
            ),
        )
        db.commit()

    # Send email via SES
    from .ses import send_reset_code
    return send_reset_code(email, code)


def verify_reset_code(email: str, code: str) -> bool:
    """Verify a reset code is valid (not expired, not used, attempts < max)."""
    email = email.strip().lower()
    code_hash = hashlib.sha256(code.strip().encode()).hexdigest()

    with get_db() as db:
        row = db.execute(
            "SELECT id, code_hash, expires_at, attempts, used FROM password_reset_codes "
            "WHERE email=? AND used=0 ORDER BY expires_at DESC LIMIT 1",
            (email,),
        ).fetchone()

    if not row:
        return False

    row_id = row[0] if isinstance(row, tuple) else row["id"]
    stored_hash = row[1] if isinstance(row, tuple) else row["code_hash"]
    expires_at = row[2] if isinstance(row, tuple) else row["expires_at"]
    attempts = row[3] if isinstance(row, tuple) else row["attempts"]

    # Check expiry
    if isinstance(expires_at, str):
        exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    else:
        exp_dt = expires_at
    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp_dt:
        return False

    # Increment attempts
    with get_db() as db:
        db.execute(
            "UPDATE password_reset_codes SET attempts=attempts+1 WHERE id=?",
            (row_id,),
        )
        db.commit()

    # Too many attempts — burn the code
    if attempts >= RESET_MAX_ATTEMPTS:
        with get_db() as db:
            db.execute(
                "UPDATE password_reset_codes SET used=1 WHERE id=?", (row_id,)
            )
            db.commit()
        return False

    return stored_hash == code_hash


def reset_password(email: str, code: str, new_password: str) -> bool:
    """Verify code and set new password. Returns True on success."""
    if len(new_password) < 8:
        raise AuthError("Password must be at least 8 characters", "weak_password")

    if not verify_reset_code(email, code):
        raise AuthError("Invalid or expired code", "invalid_code")

    email = email.strip().lower()
    code_hash = hashlib.sha256(code.strip().encode()).hexdigest()

    # Mark code as used
    with get_db() as db:
        db.execute(
            "UPDATE password_reset_codes SET used=1 WHERE email=? AND code_hash=? AND used=0",
            (email, code_hash),
        )
        db.commit()

    # Update password
    pw_hash = _hash_password(new_password)
    with get_db() as db:
        db.execute(
            "UPDATE users SET password_hash=? WHERE email=?", (pw_hash, email)
        )
        db.commit()

    # Invalidate all sessions (force re-login)
    user = get_user_by_email(email)
    if user:
        logout(user.id)

    return True
