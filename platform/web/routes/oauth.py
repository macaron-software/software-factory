"""
OAuth routes — GitHub and Azure AD login flows.

Endpoints:
    GET  /auth/github          — redirect to GitHub OAuth
    GET  /auth/github/callback — handle GitHub callback
    GET  /auth/azure           — redirect to Azure AD OAuth
    GET  /auth/azure/callback  — handle Azure AD callback

Env vars:
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
    AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET, AZURE_AD_TENANT_ID
"""

import os
import logging

import aiohttp
from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse, JSONResponse

from ...auth import service

logger = logging.getLogger(__name__)

router = APIRouter()

# GitHub OAuth config
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# Azure AD OAuth config
AZURE_AD_CLIENT_ID = os.environ.get("AZURE_AD_CLIENT_ID", "")
AZURE_AD_CLIENT_SECRET = os.environ.get("AZURE_AD_CLIENT_SECRET", "")
AZURE_AD_TENANT_ID = os.environ.get("AZURE_AD_TENANT_ID", "common")
AZURE_AUTHORIZE_URL = f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/oauth2/v2.0/authorize"
AZURE_TOKEN_URL = f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/oauth2/v2.0/token"
AZURE_GRAPH_URL = "https://graph.microsoft.com/v1.0/me"

ACCESS_COOKIE_MAX_AGE = 15 * 60
REFRESH_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def _set_auth_cookies(response, tokens: dict):
    response.set_cookie(
        "access_token", tokens["access_token"],
        max_age=ACCESS_COOKIE_MAX_AGE, httponly=True, samesite="lax", path="/",
    )
    response.set_cookie(
        "refresh_token", tokens["refresh_token"],
        max_age=REFRESH_COOKIE_MAX_AGE, httponly=True, samesite="lax", path="/api/auth",
    )
    return response


def _get_callback_url(request: Request, provider: str) -> str:
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.hostname)
    return f"{scheme}://{host}/auth/{provider}/callback"


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

@router.get("/auth/github")
async def github_login(request: Request):
    """Redirect to GitHub OAuth authorization."""
    if not GITHUB_CLIENT_ID:
        return JSONResponse({"error": "GitHub OAuth not configured"}, status_code=501)

    callback = _get_callback_url(request, "github")
    url = f"{GITHUB_AUTHORIZE_URL}?client_id={GITHUB_CLIENT_ID}&redirect_uri={callback}&scope=user:email"
    return RedirectResponse(url)


@router.get("/auth/github/callback")
async def github_callback(request: Request):
    """Handle GitHub OAuth callback."""
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse("/login?error=no_code")

    try:
        async with aiohttp.ClientSession() as session:
            # Exchange code for token
            async with session.post(
                GITHUB_TOKEN_URL,
                json={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                token_data = await resp.json()

            access_token = token_data.get("access_token")
            if not access_token:
                logger.warning("GitHub OAuth: no access_token in response")
                return RedirectResponse("/login?error=token_failed")

            # Fetch user profile
            async with session.get(
                GITHUB_USER_URL,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                user_data = await resp.json()

            email = user_data.get("email")
            # If email is private, fetch from /user/emails
            if not email:
                async with session.get(
                    f"{GITHUB_USER_URL}/emails",
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    emails = await resp.json()
                    for e in emails:
                        if e.get("primary") and e.get("verified"):
                            email = e["email"]
                            break
                    if not email and emails:
                        email = emails[0].get("email", "")

            if not email:
                return RedirectResponse("/login?error=no_email")

            display_name = user_data.get("name") or user_data.get("login", email.split("@")[0])
            avatar = user_data.get("avatar_url", "")

            tokens = service.oauth_login_or_create(
                email=email,
                display_name=display_name,
                auth_provider="github",
                avatar=avatar,
                ip=request.client.host if request.client else "",
                ua=request.headers.get("user-agent", ""),
            )

            next_url = request.cookies.get("oauth_next", "/")
            response = RedirectResponse(next_url)
            _set_auth_cookies(response, tokens)
            response.delete_cookie("oauth_next")
            return response

    except Exception as e:
        logger.error(f"GitHub OAuth error: {e}")
        return RedirectResponse("/login?error=oauth_failed")


# ---------------------------------------------------------------------------
# Azure AD
# ---------------------------------------------------------------------------

@router.get("/auth/azure")
async def azure_login(request: Request):
    """Redirect to Azure AD OAuth authorization."""
    if not AZURE_AD_CLIENT_ID:
        return JSONResponse({"error": "Azure AD OAuth not configured"}, status_code=501)

    callback = _get_callback_url(request, "azure")
    url = (
        f"{AZURE_AUTHORIZE_URL}?client_id={AZURE_AD_CLIENT_ID}"
        f"&response_type=code&redirect_uri={callback}"
        f"&scope=openid+profile+email+User.Read"
    )
    return RedirectResponse(url)


@router.get("/auth/azure/callback")
async def azure_callback(request: Request):
    """Handle Azure AD OAuth callback."""
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse("/login?error=no_code")

    callback = _get_callback_url(request, "azure")

    try:
        async with aiohttp.ClientSession() as session:
            # Exchange code for token
            async with session.post(
                AZURE_TOKEN_URL,
                data={
                    "client_id": AZURE_AD_CLIENT_ID,
                    "client_secret": AZURE_AD_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": callback,
                    "grant_type": "authorization_code",
                    "scope": "openid profile email User.Read",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                token_data = await resp.json()

            access_token = token_data.get("access_token")
            if not access_token:
                logger.warning("Azure AD OAuth: no access_token in response")
                return RedirectResponse("/login?error=token_failed")

            # Fetch user profile from Microsoft Graph
            async with session.get(
                AZURE_GRAPH_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                user_data = await resp.json()

            email = user_data.get("mail") or user_data.get("userPrincipalName", "")
            if not email:
                return RedirectResponse("/login?error=no_email")

            display_name = user_data.get("displayName") or email.split("@")[0]

            tokens = service.oauth_login_or_create(
                email=email,
                display_name=display_name,
                auth_provider="azure",
                ip=request.client.host if request.client else "",
                ua=request.headers.get("user-agent", ""),
            )

            next_url = request.cookies.get("oauth_next", "/")
            response = RedirectResponse(next_url)
            _set_auth_cookies(response, tokens)
            response.delete_cookie("oauth_next")
            return response

    except Exception as e:
        logger.error(f"Azure AD OAuth error: {e}")
        return RedirectResponse("/login?error=oauth_failed")
