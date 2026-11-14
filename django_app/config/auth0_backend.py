from django.contrib.auth.backends import ModelBackend


class Auth0AdminBackend(ModelBackend):
    """Mantiene los permisos Django; la autenticación ocurre en el callback OIDC."""

    def authenticate(self, request, **credentials):
        # Nunca aceptar usuario y contraseña de Django como login web.
        return None
