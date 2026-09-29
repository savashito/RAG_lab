"""
Pruebas del login con Google: tras autenticarse, el usuario vuelve a la URL que pidió
(con su query, p. ej. /conversar?tema=…), nunca a un sitio externo. Google se simula.

    uv run --all-extras --with pytest python -m pytest tests/test_auth_redirect.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "apps" / "rewrite_lab"
pytest.importorskip("authlib")
pytest.importorskip("itsdangerous")
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    monkeypatch.syspath_prepend(str(APP))
    sys.modules.pop("auth", None)
    auth = importlib.import_module("auth")
    from authlib.integrations.starlette_client import StarletteOAuth2App
    from starlette.responses import RedirectResponse

    async def fake_redirect(self, request, redirect_uri, **kw):
        return RedirectResponse("https://accounts.google.com/o/oauth2/auth?fake=1")

    async def fake_token(self, request, **kw):
        return {"userinfo": {"email": "ana@example.com", "email_verified": True, "name": "Ana"}}

    monkeypatch.setattr(StarletteOAuth2App, "authorize_redirect", fake_redirect)
    monkeypatch.setattr(StarletteOAuth2App, "authorize_access_token", fake_token)

    app = FastAPI()

    @app.get("/")
    def home():
        return {"page": "home"}

    @app.get("/conversar")
    def conversar():
        return {"page": "conversar"}

    assert auth.install_auth(app, is_allowed=lambda e: e == "ana@example.com")
    # base_url https: la cookie de sesión es https_only.
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


HTML = {"accept": "text/html"}


def _login_flow(c, first_url):
    r = c.get(first_url, headers=HTML)
    assert r.status_code in (302, 307) and r.headers["location"].endswith("/login")
    r = c.get("/login", headers=HTML)
    assert "accounts.google.com" in r.headers["location"]
    return c.get("/auth/callback?code=x&state=y", headers=HTML)


def test_returns_to_requested_url_with_query(client):
    r = _login_flow(client, "/conversar?tema=psicologia_conductual&vecinos=true")
    assert r.headers["location"] == "/conversar?tema=psicologia_conductual&vecinos=true"
    assert client.get("/conversar?tema=psicologia_conductual", headers=HTML).json() == {"page": "conversar"}


def test_without_pending_url_goes_home(client):
    client.get("/login", headers=HTML)
    r = client.get("/auth/callback?code=x&state=y", headers=HTML)
    assert r.headers["location"] == "/"


def test_login_next_param(client):
    client.get("/login?next=/conversar%3Ftema%3Dderecho_penal_mexicano", headers=HTML)
    r = client.get("/auth/callback?code=x&state=y", headers=HTML)
    assert r.headers["location"] == "/conversar?tema=derecho_penal_mexicano"


@pytest.mark.parametrize("evil", ["https://evil.com/x", "//evil.com/x", "/\\evil.com", "/login", "/logout"])
def test_rejects_external_or_loop_targets(client, evil):
    client.get("/login", params={"next": evil}, headers=HTML)
    r = client.get("/auth/callback?code=x&state=y", headers=HTML)
    assert r.headers["location"] == "/"


def test_api_calls_without_session_get_401_not_redirect(client):
    r = client.post("/conversar", json={})
    assert r.status_code == 401
