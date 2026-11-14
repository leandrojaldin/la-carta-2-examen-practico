from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.django_client import OAuth
from authlib.jose.errors import JoseError
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods


oauth = OAuth()
oauth.register(
    name='auth0',
    client_id=settings.AUTH0_CLIENT_ID,
    client_secret=settings.AUTH0_CLIENT_SECRET,
    server_metadata_url=(
        f'https://{settings.AUTH0_DOMAIN}/.well-known/openid-configuration'
    ),
    client_kwargs={'scope': 'openid profile email'},
)


def _admin_destination(next_url):
    """Solo permitir rutas internas del Admin después del callback."""
    if (
        isinstance(next_url, str)
        and next_url.startswith('/admin/')
        and not next_url.startswith('//')
        and '\\' not in next_url
        and '\r' not in next_url
        and '\n' not in next_url
    ):
        return next_url
    return reverse('admin:index')


def auth0_login(request):
    if not all((
        settings.AUTH0_DOMAIN,
        settings.AUTH0_CLIENT_ID,
        settings.AUTH0_CLIENT_SECRET,
        settings.AUTH0_DJANGO_ADMIN_SUB,
        settings.AUTH0_DJANGO_ADMIN_USERNAME,
    )):
        return HttpResponse('Falta configurar Auth0 para Django.', status=503)

    request.session['auth0_next'] = _admin_destination(request.GET.get('next'))
    callback = request.build_absolute_uri(reverse('auth0_callback'))
    return oauth.auth0.authorize_redirect(request, callback)


def auth0_callback(request):
    try:
        token = oauth.auth0.authorize_access_token(request)
    except (OAuthError, JoseError):
        return HttpResponse('No se pudo validar el inicio de sesión.', status=401)

    # Authlib verifica state, nonce, firma, emisor y audiencia del ID token.
    if not token.get('id_token'):
        return HttpResponse('Auth0 no devolvió un ID token.', status=401)

    userinfo = token.get('userinfo')
    sub = userinfo.get('sub') if userinfo else None
    if not sub or sub != settings.AUTH0_DJANGO_ADMIN_SUB:
        return HttpResponseForbidden('Esta cuenta no tiene acceso al Admin.')

    user = get_user_model().objects.filter(
        username=settings.AUTH0_DJANGO_ADMIN_USERNAME,
        is_active=True,
        is_staff=True,
        is_superuser=True,
    ).first()
    if user is None:
        return HttpResponseForbidden('El administrador Django no está habilitado.')

    destination = _admin_destination(request.session.pop('auth0_next', None))
    login(request, user, backend='config.auth0_backend.Auth0AdminBackend')
    request.session['auth0_sub'] = sub
    return HttpResponseRedirect(destination)


@require_http_methods(['GET', 'POST'])
def auth0_logout(request):
    logout(request)
    return HttpResponse(
        'Sesión de Django cerrada. '
        '<a href="/admin/">Volver al Admin</a>.'
    )
