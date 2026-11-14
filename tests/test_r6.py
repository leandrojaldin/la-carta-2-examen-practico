
import pytest
import app as proyecto
import auth0_integration

def test_sin_sesion_no_puede_crear_pedido(monkeypatch):

    proyecto.app.config["TESTING"] = True

    def creacion_prohibida(*args, **kwargs):
        pytest.fail(
            "Se intento crear un pedido sin iniciar sesion"
        )

    monkeypatch.setattr(
        proyecto,
        "crear_pedido",
        creacion_prohibida
    )

    with proyecto.app.test_client() as cliente:

        with cliente.session_transaction() as sesion:
            sesion.clear()

        respuesta = cliente.post(
            "/restaurantes/1/pedir",
            data={
                "plato_id": "1",
                "cantidad_1": "2"
            }
        )

    assert respuesta.status_code == 401

##El test simula al usuario que intenta crear un epdido sin hacer iniciado sesion

def test_cliente_no_puede_avanzar_pedido(monkeypatch):

    proyecto.app.config["TESTING"] = True

    # Simulamos el contenido de un token válido de cliente.
    def verificar_token_cliente(token):
        return {
            "sub": "auth0|cliente-de-prueba",
            "permissions": [
                "create:pedidos",
                "read:mis-pedidos"
            ]
        }

    # Solo durante esta prueba, reemplazamos la
    # verificación externa por nuestro usuario simulado.
    monkeypatch.setattr(
        auth0_integration,
        "verificar_token",
        verificar_token_cliente
    )

    monkeypatch.setattr(
        proyecto,
        "verificar_token",
        verificar_token_cliente
    )

    # Si Flask intenta cambiar el estado, la prueba falla.
    def avance_prohibido(*args, **kwargs):
        pytest.fail(
            "Un cliente consiguio llegar a la funcion de cocina"
        )

    monkeypatch.setattr(
        proyecto,
        "avanzar_estado_cocina",
        avance_prohibido
    )

    with proyecto.app.test_client() as cliente:

        with cliente.session_transaction() as sesion:
            sesion["access_token"] = "token-simulado"

        respuesta = cliente.post(
            "/cocina/pedidos/2/avanzar",
            data={"estado": "en_preparacion"}
        )

    assert respuesta.status_code == 403
