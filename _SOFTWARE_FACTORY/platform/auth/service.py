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
    db = get_db()
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


def _row_to_user(row) -> User:
    """Convert DB row to User object."""
    if isinstance(row, tuple):
        return User(
            id=row[0], email=row[1], display_name=row[3],
            role=row[4], avatar=row[5] or "", is_active=bool(row[6]),
            auth_provider=row[7] or "local", last_login=row[9], created_at=row[10],
        )
    return User(
        id=row["id"], email=row["email"], display_name=row["display_name"],
        role=row["role"], avatar=row["avatar"] or "", is_active=bool(row["is_active"]),
        auth_provider=row["auth_provider"] or "local",
        last_login=row["last_login"], created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def user_count() -> int:
    """Return total number of users (for setup wizard check)."""
    db = get_db()
    try:
        row = db.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if isinstance(row, tuple) else row[0]
    except Exception:
        return 0


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

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        raise AuthError("Email already registered", "email_taken")

    user_id = uuid.uuid4().hex[:12]
    password_hash = _hash_password(password)
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "INSERT INTO users (id, email, password_hash, display_name, role, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, email, password_hash, display_name.strip(), role, now),
    )
    db.commit()

    return User(
        id=user_id, email=email, display_name=display_name.strip(),
        role=role, created_at=now,
    )


def get_user_by_id(user_id: str) -> Optional[User]:
    """Get user by ID."""
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
    ).fetchone()
    return _row_to_user(row) if row else None


def list_users() -> list[User]:
    """List all users."""
    db = get_db()
    rows = db.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [_row_to_user(r) for r in rows]


def update_user(user_id: str, **kwargs) -> Optional[User]:
    """Update user fields. Allowed: display_name, role, avatar, is_active."""
    allowed = {"display_name", "role", "avatar", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_user_by_id(user_id)

    db = get_db()
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [user_id]
    db.execute(f"UPDATE users SET {sets} WHERE id=?", vals)
    db.commit()
    return get_user_by_id(user_id)


def delete_user(user_id: str) -> bool:
    """Delete user and related data."""
    db = get_db()
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
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO user_project_roles (user_id, project_id, role, granted_by) "
        "VALUES (?, ?, ?, ?)",
        (user_id, project_id, role, granted_by),
    )
    db.commit()


def get_project_role(user_id: str, project_id: str) -> str:
    """Get user role for a project. Falls back to global role."""
    db = get_db()
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
    db = get_db()
    rows = db.execute(
        "SELECT project_id, role FROM user_project_roles WHERE user_id=?",
        (user_id,),
    ).fetchall()
    return [
        {"project_id": r[0] if isinstance(r, tuple) else r["project_id"],
         "role": r[1] if isinstance(r, tuple) else r["role"]}
        for r in rows
    ]


def remove_project_role(user_id: str, project_id: str):
    """Remove user role for a project (falls back to global role)."""
    db = get_db()
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

    db = get_db()
    db.execute(
        "INSERT INTO user_sessions (id, user_id, refresh_token_hash, user_agent, ip_address, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, user.id, token_hash, ua[:200], ip[:45], expires.isoformat()),
    )
    db.commit()
    return token


def login(email: str, password: str, ip: str = "", ua: str = "") -> dict:
    """Authenticate user, return access + refresh tokens."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE email=? AND is_active=1", (email.strip().lower(),)
    ).fetchone()
    if not row:
        raise AuthError("Invalid credentials", "invalid_credentials")

    pw_hash = row[2] if isinstance(row, tuple) else row["password_hash"]
    if not _verify_password(password, pw_hash):
        raise AuthError("Invalid credentials", "invalid_credentials")

    user = _row_to_user(row)

    # Update last_login
    now = datetime.now(timezone.utc).isoformat()
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

    db = get_db()
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
    db = get_db()
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
    db = get_db()
    db.execute(
        "DELETE FROM user_sessions WHERE expires_at < ?",
        (datetime.now(timezone.utc).isoformat(),),
    )
    db.commit()
