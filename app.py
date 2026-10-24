import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy

from datetime import datetime, timezone

##Utentificacion 


##Registro de la api de restuarantes


from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import SQLAlchemyError

from werkzeug.middleware.proxy_fix import ProxyFix
from auth0_integration import (
    AuthError as Auth0Error,
    init_auth0,
    auth0_bp,
    manejar_error_auth0,
    requires_auth,
    verificar_token,
)
##Registro de autenticacion 

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuracion de Auth0
for variable in (
    "AUTH0_DOMAIN",
    "AUTH0_AUDIENCE",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
):
    app.config[variable] = os.environ.get(variable, "")

# Proteccion de la cookie de sesion
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
)

# En produccion, Nginx comunicara el protocolo HTTPS
if os.environ.get("BEHIND_PROXY", "0") == "1":
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
    )


db = SQLAlchemy(app)

def utcnow():
    return datetime.now(timezone.utc)


class Restaurante(db.Model):
    __tablename__ = 'restaurantes'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    ciudad = db.Column(db.String(80), nullable=False)
    direccion = db.Column(db.String(200), nullable=True)
    telefono = db.Column(db.String(30), nullable=True)

    ##Nueva columna
    capacidad = db.Column(db.Integer, nullable=False, default=50)
    

    platos = db.relationship(
    'Plato',
    backref='restaurante'
)

class Plato(db.Model):
    __tablename__ = 'platos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    precio = db.Column(db.Numeric(10, 2), db.CheckConstraint('precio > 0'), nullable=False)
    disponible = db.Column(db.Boolean, nullable=False, default=True)

    ## Nueva columna
    ingredientes = db.Column(db.Integer, nullable=False, default=50)

    restaurante_id = db.Column(db.Integer, db.ForeignKey('restaurantes.id'), nullable=False)


class Pedido(db.Model):
    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)

    cliente = db.Column(db.String(255), nullable=False)

    restaurante_id = db.Column(
        db.Integer,
        db.ForeignKey("restaurantes.id"),
        nullable=False
    )

    estado = db.Column(
        db.String(20),
        nullable=False,
        default="pendiente"
    )

    fecha = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow
    )

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00")
    )

    restaurante = db.relationship(
        "Restaurante",
        backref="pedidos"
    )

    items = db.relationship(
        "ItemPedido",
        back_populates="pedido"
    )


class ItemPedido(db.Model):
    __tablename__ = "items_pedido"

    id = db.Column(db.Integer, primary_key=True)

    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedidos.id"),
        nullable=False
    )

    plato_id = db.Column(
        db.Integer,
        db.ForeignKey("platos.id"),
        nullable=False
    )

    cantidad = db.Column(db.Integer, nullable=False)

    precio_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    pedido = db.relationship(
        "Pedido",
        back_populates="items"
    )

    plato = db.relationship("Plato")


# ==========================================
# REGLAS DE NEGOCIO DE PEDIDOS - R1
# ==========================================
class ErrorPedido(Exception):
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = codigo

def validar_entero(valor, nombre):
    if isinstance(valor , bool):
        raise ErrorPedido(f"{nombre} debe ser un entero.")

    if isinstance(valor , int):
        return valor

    if isinstance(valor , str) and valor.isascii() and valor.isdecimal():
        return int(valor)

    raise ErrorPedido("f{nombre} debe ser un entero.")


def crear_pedido(cliente_sub, restaurante_id, items_solicitados):
    """
    Crea un pedido completo en una sola transacción.

    cliente_sub debe provenir de una sesión Auth0 validada.
    Nunca se debe tomar de un campo enviado por el cliente.
    """

    try:
        if not isinstance(cliente_sub, str) or not cliente_sub.strip():
            raise ErrorPedido("Cliente no autenticado.", 401)

        restaurante = db.session.get(Restaurante, restaurante_id)

        if restaurante is None:
            raise ErrorPedido("Restaurante no encontrado.", 404)

        if not isinstance(items_solicitados, list) or not items_solicitados:
            raise ErrorPedido("El pedido necesita al menos un plato.")

        detalles = []
        total = Decimal("0.00")
        platos_repetidos = set()

        for item in items_solicitados:
            if not isinstance(item, dict):
                raise ErrorPedido("Formato de ítem inválido.")

            plato_id = validar_entero(item.get("plato_id"), "plato_id")
            cantidad = validar_entero(item.get("cantidad"), "cantidad")

            if cantidad < 1 or cantidad > 20:
                raise ErrorPedido("La cantidad debe estar entre 1 y 20.")

            if plato_id in platos_repetidos:
                raise ErrorPedido("No se puede repetir un plato.")

            platos_repetidos.add(plato_id)

            plato = db.session.get(Plato, plato_id)

            if plato is None:
                raise ErrorPedido("Plato no encontrado.", 404)

            if not plato.disponible:
                raise ErrorPedido(f"El plato {plato.nombre} no está disponible.")

            if plato.restaurante_id != restaurante.id:
                raise ErrorPedido(
                    "Todos los platos deben pertenecer al mismo restaurante."
                )

            precio = plato.precio
            subtotal = precio * cantidad

            total += subtotal
            detalles.append((plato.id, cantidad, precio))

        pedido = Pedido(
            cliente=cliente_sub,
            restaurante_id=restaurante.id,
            estado="pendiente",
            total=total
        )

        db.session.add(pedido)
        db.session.flush()

        for plato_id, cantidad, precio in detalles:
            db.session.add(
                ItemPedido(
                    pedido_id=pedido.id,
                    plato_id=plato_id,
                    cantidad=cantidad,
                    precio_unitario=precio
                )
            )

        db.session.commit()
        return pedido

    except Exception:
        db.session.rollback()
        raise


# ==========================================
# TRANSICIONES DE ESTADO - R1
# ==========================================

TRANSICIONES_COCINA = {
    "pendiente": "en_preparacion",
    "en_preparacion": "listo",
    "listo": "entregado",
}

def avanzar_estado_cocina(pedido_id, estado_solicitado=None):
    """
    Avanza un pedido un solo estado.

    La autorización del rol cocina debe comprobarse
    en la ruta HTTP mediante Auth0.
    """
    try:
        pedido = (
            db.session.query(Pedido)
            .filter(Pedido.id == pedido_id)
            .with_for_update()
            .one_or_none()
        )

        if pedido is None:
            raise ErrorPedido("Pedido no encontrado.", 404)

        siguiente_estado = TRANSICIONES_COCINA.get(pedido.estado)

        if siguiente_estado is None:
            raise ErrorPedido(
                "Este pedido no puede avanzar de estado."
            )

        if (
        estado_solicitado is not None
        and estado_solicitado != siguiente_estado
        ):
            raise ErrorPedido(
            "Transicion de estado no permitida."
        )

        pedido.estado = siguiente_estado

        db.session.commit()
        return pedido

    except Exception:
        db.session.rollback()
        raise


def cancelar_pedido_cliente(pedido_id, cliente_sub):
    """
    Solo el propietario puede cancelar su pedido
    y únicamente si está pendiente.
    """
    if not isinstance(cliente_sub, str) or not cliente_sub.strip():
        raise ErrorPedido("Cliente no autenticado.", 401)

    try:
        pedido = (
            db.session.query(Pedido)
            .filter(
                Pedido.id == pedido_id,
                Pedido.cliente == cliente_sub
            )
            .with_for_update()
            .one_or_none()
        )

        if pedido is None:
            raise ErrorPedido("Pedido no encontrado.", 404)

        if pedido.estado != "pendiente":
            raise ErrorPedido(
                "Solo se pueden cancelar pedidos pendientes."
            )

        pedido.estado = "cancelado"

        db.session.commit()
        return pedido

    except Exception:
        db.session.rollback()
        raise

# ==========================================
# REGISTRO DE AUTENTICACION AUTH0 - R2
# ==========================================

init_auth0(app)

app.register_blueprint(auth0_bp)

app.register_error_handler(
    Auth0Error,
    manejar_error_auth0,
)


@app.context_processor
def compartir_permisos():
    """Hace disponibles los permisos en las plantillas HTML."""
    token = session.get("access_token")

    if not token:
        return {"permisos": []}

    try:
        payload = verificar_token(token)
        permisos = payload.get("permissions", [])
        return {
            "permisos": permisos if isinstance(permisos, list) else []
        }
    except Auth0Error:
        return {"permisos": []}



# INICIO DEL CRUD DE RESTAURANTES
@app.route('/restaurantes', methods=['GET'])
def listar_restaurantes():
    ciudad_Filtro = request.args.get('ciudad')

    if ciudad_Filtro:
        lista = Restaurante.query.filter(Restaurante.ciudad.ilike(f'%{ciudad_Filtro}%')).all()
    else:
        lista = Restaurante.query.all()

    return render_template('restaurantes/index.html', restaurantes=lista)


@app.route('/restaurantes/crear', methods=['GET', 'POST'])
@requires_auth("write:carta")
def crear_restaurante(payload):
    if request.method == 'POST':
        nuevo_restaurante = Restaurante(
            nombre=request.form.get('nombre'),
            ciudad=request.form.get('ciudad'),
            direccion=request.form.get('direccion', ''),
            telefono=request.form.get('telefono', '')
        )
        try:
            db.session.add(nuevo_restaurante)
            db.session.commit()
            flash(f'Sucursal "{nuevo_restaurante.nombre}" creada con éxito')
            return redirect(url_for('listar_restaurantes'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear la sucursal: {e}")
            return redirect(url_for('crear_restaurante'))

    return render_template('restaurantes/formulario.html', restaurante=None)


@app.route('/restaurantes/<int:restaurante_id>', methods=['GET'])
def detalle_restaurante(restaurante_id):
    restaurante_encontrado = Restaurante.query.get_or_404(restaurante_id)
    return render_template('restaurantes/detalle.html', restaurante=restaurante_encontrado)


@app.route('/restaurantes/<int:restaurante_id>/editar', methods=['GET', 'POST'])
@requires_auth("write:carta")
def editar_restaurante(payload, restaurante_id):
    restaurante_encontrado = Restaurante.query.get_or_404(restaurante_id)

    if request.method == 'POST':
        restaurante_encontrado.nombre = request.form.get('nombre')
        restaurante_encontrado.ciudad = request.form.get('ciudad')
        restaurante_encontrado.direccion = request.form.get('direccion')
        restaurante_encontrado.telefono = request.form.get('telefono')

        try:
            db.session.commit()
            flash(f'Sucursal "{restaurante_encontrado.nombre}" actualizada con éxito')
            return redirect(url_for('detalle_restaurante', restaurante_id=restaurante_encontrado.id))
        except:
            db.session.rollback()
            flash('Error al actualizar la sucursal.')
            return redirect(url_for('editar_restaurante', restaurante_id=restaurante_encontrado.id))

    return render_template('restaurantes/formulario.html', restaurante=restaurante_encontrado)

@app.route('/restaurantes/<int:restaurante_id>/eliminar', methods=['POST'])
@requires_auth("delete:carta")
def eliminar_restaurante(payload, restaurante_id):
    restaurante_encontrado = Restaurante.query.get_or_404(restaurante_id)
    try:
        db.session.delete(restaurante_encontrado)
        db.session.commit()
        flash(f'Sucursal "{restaurante_encontrado.nombre}" eliminada correctamente')
    except:
        db.session.rollback()
        flash('Error al eliminar Sucursal')

    return redirect(url_for('listar_restaurantes'))

# ==========================================
# FIN DEL CRUD DE RESTAURANTES
# ==========================================


# RUTA PARA AGREGAR PLATOS AL MENÚ
@app.route('/restaurantes/<int:restaurante_id>/platos', methods=['POST'])
@requires_auth("write:carta")
def agregar_plato(payload, restaurante_id):
    restaurante_encontrado = Restaurante.query.get_or_404(restaurante_id)

    if request.method == 'POST':
        nuevo_nombre_plato = request.form.get('nombre')
        nuevo_precio_plato = request.form.get('precio')

        nuevo_plato = Plato(
            nombre=nuevo_nombre_plato,
            precio=float(nuevo_precio_plato),
            restaurante_id=restaurante_encontrado.id
        )

        try:
            db.session.add(nuevo_plato)
            db.session.commit()
            flash(f'Plato "{nuevo_nombre_plato}" agregado al menú')
        except:
            db.session.rollback()
            flash('Error al agregar el plato')

    return redirect(url_for('detalle_restaurante', restaurante_id=restaurante_encontrado.id))


# ==========================================
# R2 - EDITAR PLATOS (ADMIN)
# ==========================================

@app.route("/platos/<int:plato_id>/editar", methods=["GET", "POST"])
@requires_auth("write:carta") 
def editar_plato(payload, plato_id):

    plato = db.get_or_404(Plato, plato_id)

    if request.method == "GET":
        return render_template(
            "restaurantes/editar_plato.html",
            plato=plato,
            error=None
        )

    nombre = request.form.get("nombre", "").strip()
    precio_texto = request.form.get("precio", "").strip()

    if not nombre or len(nombre) > 120:
        return render_template(
            "restaurantes/editar_plato.html",
            plato=plato,
            error="El nombre debe tener entre 1 y 120 caracteres."
        ), 400

    try:
        precio = Decimal(precio_texto)
    except InvalidOperation:
        return render_template(
            "restaurantes/editar_plato.html",
            plato=plato,
            error="El precio debe ser un numero valido."
        ), 400

    if (
        not precio.is_finite()
        or precio <= 0
        or precio > Decimal("99999999.99")
        or precio != precio.quantize(Decimal("0.01"))
    ):
        return render_template(
            "restaurantes/editar_plato.html",
            plato=plato,
            error="El precio debe ser positivo y tener maximo dos decimales."
        ), 400

    try:
        plato.nombre = nombre
        plato.precio = precio
        plato.disponible = "disponible" in request.form

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Error al editar plato %s", plato_id)

        return "Error al guardar el plato.", 500

    return redirect(
        url_for(
            "detalle_restaurante",
            restaurante_id=plato.restaurante_id
        ),
        code=303
    )



# ==========================================
# R2 - ELIMINAR O RETIRAR PLATOS
# ==========================================


# ==========================================
# R2 - ELIMINAR O RETIRAR PLATOS
# ==========================================

@app.post("/platos/<int:plato_id>/eliminar")
@requires_auth("delete:carta")
def eliminar_plato(payload, plato_id):

    plato = db.get_or_404(Plato, plato_id)

    restaurante_id = plato.restaurante_id
    nombre_plato = plato.nombre

    try:
        # Comprobar si el plato aparece en pedidos.
        tiene_pedidos = (
            db.session.query(ItemPedido.id)
            .filter(ItemPedido.plato_id == plato_id)
            .first()
            is not None
        )

        if tiene_pedidos:
            # No borrar los datos historicos.
            plato.disponible = False
            mensaje = (
                f'Plato "{nombre_plato}" retirado de la carta. '
                'Se conservaron sus pedidos historicos.'
            )
        else:
            # Si nunca fue pedido, puede eliminarse.
            db.session.delete(plato)
            mensaje = (
                f'Plato "{nombre_plato}" eliminado correctamente.'
            )

        db.session.commit()
        flash(mensaje)

    except SQLAlchemyError:
        db.session.rollback()

        app.logger.exception(
            "Error al eliminar plato %s",
            plato_id
        )

        return render_template(
            "auth0_error.html",
            status=500,
            mensaje="No se pudo eliminar el plato."
        ), 500

    return redirect(
        url_for(
            "detalle_restaurante",
            restaurante_id=restaurante_id
        ),
        code=303
    )



# ==========================================
# PEDIDOS WEB - R1 Y R2
# ==========================================

@app.get("/restaurantes/<int:restaurante_id>/pedir")
def formulario_pedido(restaurante_id):
    restaurante = db.get_or_404(Restaurante, restaurante_id)

    platos = Plato.query.filter_by(
        restaurante_id=restaurante_id,
        disponible=True
    ).order_by(Plato.id).all()

    return render_template(
        "pedidos/nuevo.html",
        restaurante=restaurante,
        platos=platos
    )


@app.post("/restaurantes/<int:restaurante_id>/pedir")
@requires_auth("create:pedidos")
def guardar_pedido_web(payload, restaurante_id):
    items = []

    for plato_id in request.form.getlist("plato_id"):
        items.append({
            "plato_id": plato_id,
            "cantidad": request.form.get(
                f"cantidad_{plato_id}", ""
            )
        })

    try:
        pedido = crear_pedido(
            cliente_sub=payload["sub"],
            restaurante_id=restaurante_id,
            items_solicitados=items
        )
    except ErrorPedido as error:
        return render_template(
            "auth0_error.html",
            status=error.codigo,
            mensaje=str(error)
        ), error.codigo

    return redirect(
        url_for(
            "detalle_pedido_cliente",
            pedido_id=pedido.id
        ),
        code=303
    )


@app.get("/pedidos/<int:pedido_id>")
@requires_auth("read:mis-pedidos")
def detalle_pedido_cliente(payload, pedido_id):
    pedido = Pedido.query.filter_by(
        id=pedido_id,
        cliente=payload["sub"]
    ).first_or_404()

    return render_template(
        "pedidos/detalle.html",
        pedido=pedido
    )

# ==========================================
# MIS PEDIDOS - CLIENTE
# ==========================================

@app.get("/mis-pedidos")
@requires_auth("read:mis-pedidos")
def mis_pedidos(payload):
    pedidos = (
        Pedido.query
        .filter_by(cliente=payload["sub"])
        .order_by(Pedido.fecha.desc())
        .all()
    )

    return render_template(
        "pedidos/mis_pedidos.html",
        pedidos=pedidos
    )


@app.post("/pedidos/<int:pedido_id>/cancelar")
@requires_auth("read:mis-pedidos")
def cancelar_pedido_web(payload, pedido_id):
    try:
        cancelar_pedido_cliente(
            pedido_id=pedido_id,
            cliente_sub=payload["sub"]
        )

    except ErrorPedido as error:
        return render_template(
            "auth0_error.html",
            status=error.codigo,
            mensaje=str(error)
        ), error.codigo

    return redirect(url_for("mis_pedidos"), code=303)


# ==========================================
# COLA DE COCINA
# ==========================================

@app.get("/cocina")
@requires_auth("read:pedidos")
def cola_cocina(payload):
    pedidos = (
        Pedido.query
        .filter(
            Pedido.estado.in_([
                "pendiente",
                "en_preparacion",
                "listo"
            ])
        )
        .order_by(Pedido.fecha.asc())
        .all()
    )

    return render_template(
        "pedidos/cocina.html",
        pedidos=pedidos,
        transiciones=TRANSICIONES_COCINA
    )


@app.post("/cocina/pedidos/<int:pedido_id>/avanzar")
@requires_auth("update:pedidos")
def avanzar_pedido_web(payload, pedido_id):
    try:
        datos = (
            request.get_json(silent=True) or {}
            if request.is_json
            else request.form
        )

        avanzar_estado_cocina(
            pedido_id,
            estado_solicitado=datos.get("estado")
        )

    except ErrorPedido as error:
        return render_template(
            "auth0_error.html",
            status=error.codigo,
            mensaje=str(error)
        ), error.codigo

    return redirect(url_for("cola_cocina"), code=303)

# ==========================================
# LOGIN CON AUTH0
# ==========================================

@app.get("/login")
def login():
    return redirect(url_for("auth0.login_auth0"))

# ==========================================
# FIN DEL FLUJO DE AUTENTICACIÓN
# ==========================================




# RUTA DE INICIO
@app.route('/', methods=['GET'])
def inicio():
    return redirect(url_for('listar_restaurantes'))


# ==========================================
# MANEJO DE ERRORES
# ==========================================
@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('errores/404.html'), 404

@app.errorhandler(500)
def error_interno(e):
    return render_template('errores/500.html'), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
