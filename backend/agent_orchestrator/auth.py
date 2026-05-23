"""
Google OAuth 2.0 + JWT session management for CrowdGuard Command.
Only emails in ALLOWED_ADMINS are granted access.
"""
import logging
import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 8

ALLOWED_ADMINS: set[str] = set(
    e.strip().lower()
    for e in os.getenv("ALLOWED_ADMINS", "").split(",")
    if e.strip()
)

ROLE_MAP: dict[str, str] = {
    e.strip().lower(): role.strip()
    for entry in os.getenv("ADMIN_ROLES", "").split(",")
    if ":" in entry
    for e, role in [entry.strip().split(":", 1)]
}


def get_google_auth_url(state: str = "") -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code_for_user(code: str) -> dict:
    """Exchange OAuth code for user info. Raises HTTPException if unauthorized."""
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="OAuth token exchange failed")
        tokens = token_resp.json()

        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to fetch user info")
        user = user_resp.json()

    email = user.get("email", "").lower()

    if ALLOWED_ADMINS and email not in ALLOWED_ADMINS:
        logger.warning(f"Unauthorized login attempt: {email}")
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: {email} is not an authorized admin",
        )

    role = ROLE_MAP.get(email, "OPERATOR")
    return {
        "email": email,
        "name": user.get("name", ""),
        "picture": user.get("picture", ""),
        "role": role,
    }


def create_jwt(user: dict) -> str:
    payload = {
        **user,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session: {e}")


def get_current_user(request: Request) -> dict:
    """Extract and verify JWT from cookie. Raises 401 if missing/invalid."""
    token = request.cookies.get("cg_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_jwt(token)


def require_super_admin(request: Request) -> dict:
    user = get_current_user(request)
    if user.get("role") != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="SUPER_ADMIN role required")
    return user
