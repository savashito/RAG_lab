"""
core/auth.py — auth guard helpers and OAuth client setup

Only infrastructure lives here:
  - oauth client (used by routers/auth.py)
  - get_current_user / require_user (used by all routers)

Routes live in routers/auth.py
"""

from fastapi import HTTPException, Request
from authlib.integrations.starlette_client import OAuth

from core.config import settings
from models.user import SessionUser
# ── OAuth client (shared with routers/auth.py) ────────────────────────────────

oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

oauth.register(
    name="facebook",
    client_id=settings.facebook_client_id,
    client_secret=settings.facebook_client_secret,
    access_token_url="https://graph.facebook.com/oauth/access_token",
    authorize_url="https://www.facebook.com/dialog/oauth",
    api_base_url="https://graph.facebook.com/",
    client_kwargs={"scope": "email"},
)

# ── Guards ────────────────────────────────────────────────────────────────────

def get_current_user(request: Request) -> SessionUser | None:
    return request.session.get("user")


def require_user(request: Request) -> SessionUser:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user