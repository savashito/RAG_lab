"""
apps/rewrite_lab/auth.py — puerta de autenticación con Google (OAuth 2 / OIDC).

Primer paso de acceso al app: cualquier ruta (salvo las de login) exige una sesión
con un correo de la **lista blanca**. El flujo es OIDC estándar contra Google:
  /login  → redirige a Google · /auth/callback → valida el correo y crea la sesión.

Se configura por variables de entorno (ver .env.example):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET   credenciales del OAuth Client (Google Cloud)
  SESSION_SECRET                           llave para firmar la cookie de sesión
  ALLOWED_EMAILS                           correos permitidos, separados por coma
  OAUTH_REDIRECT_URL                       (opcional) URL absoluta del callback,
                                           p. ej. https://legis.tlacua.cloud/auth/callback

Si faltan GOOGLE_CLIENT_ID o SESSION_SECRET, la puerta NO se instala (modo local sin
auth): así el desarrollo en la laptop sigue funcionando sin credenciales.
"""

from __future__ import annotations

import os

from authlib.integrations.starlette_client import OAuth
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

ALLOWED_EMAILS = {e.strip().lower() for e in os.environ.get('ALLOWED_EMAILS', '').split(',') if e.strip()}
SESSION_SECRET = os.environ.get('SESSION_SECRET', '')
CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
REDIRECT_URL = os.environ.get('OAUTH_REDIRECT_URL', '')

# Rutas accesibles sin sesión (el propio flujo de login y un health check).
PUBLIC_PATHS = {'/login', '/auth/callback', '/logout', '/healthz'}

_DENIED = (
    '<html><body style="font:16px system-ui;background:#0f1115;color:#e6e6e6;padding:40px">'
    '<h2>Acceso denegado</h2><p><b>{email}</b> no está en la lista de autorizados.</p>'
    '<p><a style="color:#3b82f6" href="/logout">Cerrar sesión y probar con otra cuenta</a></p>'
    '</body></html>'
)


def _email(request) -> str | None:
    return (request.session.get('user') or {}).get('email')


def install_auth(app) -> bool:
    """Instala la puerta OAuth en la app FastAPI. Devuelve True si quedó activa."""
    if not (CLIENT_ID and CLIENT_SECRET and SESSION_SECRET):
        print('AUTH: desactivada (faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / SESSION_SECRET).')
        return False

    oauth = OAuth()
    oauth.register(
        name='google',
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    async def gate(request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or _email(request):
            return await call_next(request)
        # Sin sesión: las peticiones de API (POST/JSON) reciben 401; la navegación, redirect.
        if request.method != 'GET' or 'text/html' not in request.headers.get('accept', ''):
            return JSONResponse({'error': 'no autenticado'}, status_code=401)
        return RedirectResponse('/login')

    # El orden importa: SessionMiddleware debe envolver a la puerta (se agrega después,
    # queda por fuera) para que request.session ya exista cuando `gate` lo lee.
    app.add_middleware(BaseHTTPMiddleware, dispatch=gate)
    app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET,
                       https_only=True, same_site='lax')

    @app.get('/login')
    async def login(request):
        redirect_uri = REDIRECT_URL or str(request.url_for('auth_callback'))
        return await oauth.google.authorize_redirect(request, redirect_uri)

    @app.get('/auth/callback', name='auth_callback')
    async def auth_callback(request):
        try:
            token = await oauth.google.authorize_access_token(request)
        except Exception as e:
            return HTMLResponse(f'<p>Error de OAuth: {e}</p><a href="/login">reintentar</a>', status_code=400)
        info = token.get('userinfo') or {}
        email = (info.get('email') or '').lower()
        if not info.get('email_verified', False) or (ALLOWED_EMAILS and email not in ALLOWED_EMAILS):
            return HTMLResponse(_DENIED.format(email=email or '(sin correo)'), status_code=403)
        request.session['user'] = {'email': email, 'name': info.get('name', '')}
        return RedirectResponse('/')

    @app.get('/logout')
    async def logout(request):
        request.session.clear()
        return RedirectResponse('/login')

    print(f'AUTH: activa · {len(ALLOWED_EMAILS)} correo(s) en la lista blanca.')
    return True
