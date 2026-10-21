# La Carta 2.0 — Examen Práctico de Aplicaciones Web

## Descripción

La Carta 2.0 es una aplicación para la gestión de restaurantes, platos y pedidos, desarrollada con Flask, Django, PostgreSQL, Docker Compose y Auth0.

El proyecto extiende La Carta original para incorporar pedidos con transacciones, autenticación y autorización mediante permisos.

## Tecnologías utilizadas

- **Flask:** aplicación web, lógica de pedidos y rutas HTTP.
- **Django:** modelos, migraciones y panel administrativo.
- **PostgreSQL 16:** base de datos compartida.
- **SQLAlchemy:** acceso a las tablas desde Flask.
- **Auth0 y Authlib:** inicio de sesión y autorización.
- **Docker Compose:** ejecución coordinada de los servicios.
- **Gunicorn:** servidor de aplicación.

## Arquitectura y decisiones técnicas

### Una sola base de datos

Flask y Django utilizan la misma base PostgreSQL.

Django es el único responsable de definir y modificar el esquema mediante sus modelos y migraciones. Flask utiliza SQLAlchemy para mapear las tablas existentes.

Esta decisión evita que dos sistemas de migración intenten modificar las mismas tablas.

### Modelos principales

- **Restaurante:** información del restaurante.
- **Plato:** pertenece a un restaurante, tiene precio y disponibilidad.
- **Pedido:** contiene cliente, restaurante, estado, fecha y total.
- **ItemPedido:** contiene pedido, plato, cantidad y precio_unitario.

El cliente se identifica mediante el atributo `sub` del token de Auth0.

### Reglas de los pedidos

El servidor comprueba que:

- El pedido tenga al menos un ítem.
- Todos los platos pertenezcan al restaurante seleccionado.
- Los platos existan y estén disponibles.
- Las cantidades sean números enteros entre 1 y 20.
- El precio unitario se copie desde la base de datos.
- El total se calcule en el servidor.

La creación se realiza dentro de una transacción. Si ocurre un error, se ejecuta `rollback()` para evitar guardar pedidos incompletos.

Los estados permitidos son `pendiente`, `en_preparacion`, `listo`, `entregado` y `cancelado`.

### Precio histórico

Cada `ItemPedido` almacena su propio `precio_unitario`.

Esto permite mantener el precio original aunque posteriormente cambie el precio del plato.

### Autenticación y permisos

El inicio de sesión utiliza Auth0 mediante el flujo Authorization Code con Authlib.

Flask valida los tokens y comprueba sus permisos mediante el decorador `@requires_auth()`.

Permisos configurados:

| Rol | Permisos |
|---|---|
| cliente | `create:pedidos`, `read:mis-pedidos` |
| cocina | `read:pedidos`, `update:pedidos` |
| admin | `read:pedidos`, `write:carta`, `delete:carta` |

Las páginas públicas de la carta no requieren autenticación.

### Por qué un pedido ajeno devuelve 404

Cuando un cliente solicita el detalle de un pedido, Flask consulta tanto el identificador del pedido como el `sub` del usuario autenticado.

Si el pedido no pertenece al cliente, devuelve **404** en lugar de **403** para no revelar si el pedido existe.

Los permisos también se comprueban en el servidor, independientemente de que los botones estén ocultos en la interfaz.

## Ejecución local

El proyecto requiere Docker, Docker Compose y credenciales propias de Auth0.

La configuración privada debe guardarse en `.env`, sin subir contraseñas ni secretos al repositorio.

Variables relevantes:

- `AUTH0_DOMAIN`
- `AUTH0_AUDIENCE`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `SECRET_KEY`
- Variables de conexión a PostgreSQL

Para construir e iniciar los servicios:

`docker compose up -d --build`

La aplicación Flask se encuentra disponible localmente en:

`http://localhost:5001/restaurantes`

Para detener los servicios sin eliminar el volumen de PostgreSQL:

`docker compose down`

## Funcionalidades implementadas

- Listado y detalle público de restaurantes.
- Gestión de restaurantes y platos mediante Flask.
- Autenticación real con Auth0.
- Protección de rutas mediante permisos.
- Creación de pedidos con precios calculados en el servidor.
- Visualización del detalle del pedido.
- Listado de pedidos propios del cliente.
- Cancelación de pedidos pendientes.
- Rutas de cocina para consultar y avanzar estados.
- Visualización de pedidos e ítems desde Django Admin.
- Restricciones de integridad en PostgreSQL.

## Comprobaciones realizadas

Se verificaron los siguientes casos durante el desarrollo:

1. Creación de un pedido con dos sopas de maní y una Coca cola, total Bs 60,00.
2. Acceso del cliente a sus pedidos.
3. Rechazo con HTTP 403 al intentar entrar a cocina con un usuario cliente.
4. Conservación del precio histórico al cambiar temporalmente el precio de un plato de Bs 25 a Bs 35.
5. Rechazo en PostgreSQL de un estado inválido mediante `CHECK`.
6. Registro y consulta de pedidos compartidos entre Flask y Django.

Estas verificaciones no sustituyen la batería completa de pruebas automatizadas.

## Estado y limitaciones de la entrega

Esta versión contiene el avance funcional desarrollado durante el examen práctico.

Quedaron pendientes de completar o verificar:

- Pruebas integrales con usuarios independientes de cocina y administrador.
- Todos los casos negativos y las seis pruebas automatizadas con pytest.
- Ajustes de edición de ítems dentro de Django Admin.
- Revisión completa de la gestión de platos.
- Despliegue público en EC2 con Nginx, dos subdominios y HTTPS.

No se declara completado el despliegue HTTPS ni una cobertura de pruebas que todavía no se ha demostrado.

## Estructura principal del proyecto

- `app.py`: modelos SQLAlchemy, rutas Flask y lógica de negocio.
- `auth0_integration.py`: integración y autorización Auth0.
- `django_app/carta/models.py`: modelos y restricciones de Django.
- `django_app/carta/admin.py`: configuración del panel administrativo.
- `templates/`: páginas HTML de restaurantes, pedidos y autenticación.
- `docker-compose.yml`: servicios y dependencias de ejecución.
- `requirements.txt`: dependencias de Python.

## Consideraciones de seguridad

Las credenciales y secretos se mantienen fuera del repositorio mediante archivos de entorno no versionados.

El servidor valida las identidades y los permisos, y no acepta precios enviados por el cliente.

Los datos de otros clientes se protegen mediante consultas filtradas por el `sub` autenticado.
