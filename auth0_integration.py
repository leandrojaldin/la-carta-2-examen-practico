
from functools import wraps
from urllib.parse import urlencode

import jwt
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from flask import (
    Blueprint, current_app, jsonify, redirect,
    render_template, request, session, url_for
)

auth0_bp = Blueprint("auth0", __name__, url_prefix="/auth")


class AuthError(Exception):
    def __init__(self, mensaje, status_code):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code


def init_auth0(app):
    """Configura Authlib y las claves publicas de Auth0."""
    obligatorias = (
        "AUTH0_DOMAIN",
        "AUTH0_AUDIENCE",
        "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET",
    )

    for variable in obligatorias:
        if not app.config.get(variable):
            raise RuntimeError(f"Falta configurar {variable}")

    dominio = app.config["AUTH0_DOMAIN"]

    oauth = OAuth(app)
    oauth.register(
        name="auth0",
        client_id=app.config["AUTH0_CLIENT_ID"],
        client_secret=app.config["AUTH0_CLIENT_SECRET"],
        client_kwargs={"scope": "openid profile email"},
        server_metadata_url=(
            f"https://{dominio}/.well-known/openid-configuration"
        ),
    )

    app.extensions["auth0_jwks"] = jwt.PyJWKClient(
        f"https://{dominio}/.well-known/jwks.json",
        cache_keys=True,
        timeout=5,
    )


def cliente_auth0():
    return current_app.extensions[
        "authlib.integrations.flask_client"
    ].auth0


def verificar_token(token):
    """Verifica firma RS256, expiracion, audiencia e issuer."""
    try:
        llave = current_app.extensions[
            "auth0_jwks"
        ].get_signing_key_from_jwt(token)

        return jwt.decode(
            token,
            llave.key,
            algorithms=["RS256"],
            audience=current_app.config["AUTH0_AUDIENCE"],
            issuer=(
                f"https://{current_app.config['AUTH0_DOMAIN']}/"
            ),
            options={"require": ["exp", "iat", "sub"]},
        )

    except jwt.ExpiredSignatureError:
        raise AuthError("La sesion ha expirado.", 401)

    except jwt.PyJWKClientConnectionError:
        raise AuthError("No se pudo consultar Auth0.", 503)

    except jwt.PyJWKClientError:
        raise AuthError("Clave del token no valida.", 401)

    except jwt.InvalidTokenError:
        raise AuthError("Token no valido.", 401)


def requires_auth(permiso=""):
    """Protege rutas mediante permisos del access token."""

    def decorador(funcion):
        @wraps(funcion)
        def wrapper(*args, **kwargs):
            token = session.get("access_token")

            if not token:
                raise AuthError("Debes iniciar sesion.", 401)

            payload = verificar_token(token)

            if "permissions" not in payload:
                raise AuthError(
                    "El token no contiene permisos.", 400
                )

            if permiso and permiso not in payload["permissions"]:
                raise AuthError(
                    "No tienes permiso para esta accion.", 403
                )

            return funcion(payload, *args, **kwargs)

        return wrapper

    return decorador


def manejar_error_auth0(error):
    if error.status_code == 401:
        session.pop("access_token", None)

    return render_template(
        "auth0_error.html",
        status=error.status_code,
        mensaje=error.mensaje,
    ), error.status_code


def ruta_segura(destino):
    if (
        destino
        and destino.startswith("/")
        and not destino.startswith("//")
        and "\\" not in destino
        and "\r" not in destino
        and "\n" not in destino
    ):
        return destino

    return url_for("inicio")


@auth0_bp.get("/login")
def login_auth0():
    session["next"] = ruta_segura(request.args.get("next"))

    return cliente_auth0().authorize_redirect(
        redirect_uri=url_for(
            "auth0.callback_auth0", _external=True
        ),
        audience=current_app.config["AUTH0_AUDIENCE"],
    )


@auth0_bp.get("/callback")
def callback_auth0():
    try:
        token = cliente_auth0().authorize_access_token()
    except OAuthError:
        raise AuthError("No se pudo completar el login.", 401)

    access_token = token.get("access_token")
    if not access_token:
        raise AuthError("Auth0 no devolvio el token.", 401)

    # No confiar en un token sin verificar.
    verificar_token(access_token)

    destino = session.pop("next", None) or url_for("inicio")
    perfil = token.get("userinfo") or {}

    session.clear()
    session["access_token"] = access_token
    session["user"] = {
        "name": perfil.get("name") or perfil.get("email"),
        "email": perfil.get("email"),
    }

    return redirect(destino)


@auth0_bp.post("/logout")
def logout_auth0():
    session.clear()

    parametros = urlencode({
        "returnTo": url_for("inicio", _external=True),
        "client_id": current_app.config["AUTH0_CLIENT_ID"],
    })

    dominio = current_app.config["AUTH0_DOMAIN"]

    return redirect(
        f"https://{dominio}/v2/logout?{parametros}"
    )


@auth0_bp.get("/quien-soy")
@requires_auth()
def quien_soy(payload):
    """Permite comprobar los permisos reales del usuario."""
    return jsonify({
        "sub": payload["sub"],
        "permissions": payload["permissions"],
    })
