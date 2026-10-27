
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

El proyecto requiere Git, Docker Desktop (o Docker Engine con Compose v2) y una aplicación de Auth0 configurada.

En PowerShell de Windows:

```powershell
git clone https://github.com/leandrojaldin/la-carta-2-examen-practico.git
cd la-carta-2-examen-practico
Copy-Item .env.example .env
```

Editar el nuevo archivo `.env` y reemplazar los valores `REEMPLAZAR` por credenciales propias o las proporcionadas **de forma privada** para la evaluación:

| Variable | Uso |
|---|---|
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL. |
| `SECRET_KEY` | Clave para las sesiones y configuración de las aplicaciones. |
| `JWT_SECRET_KEY` | Variable requerida por la configuración del proyecto. |
| `AUTH0_DOMAIN` | Dominio del tenant, sin `https://`. |
| `AUTH0_AUDIENCE` | Identificador exacto de la API en Auth0. |
| `AUTH0_CLIENT_ID` | Client ID de la aplicación Auth0. |
| `AUTH0_CLIENT_SECRET` | Client Secret de la aplicación Auth0. |
| `SESSION_COOKIE_SECURE` | `0` en HTTP local, `1` con HTTPS. |
| `BEHIND_PROXY` | `0` en Docker local, `1` detrás de Nginx. |

Para construir e iniciar los servicios con Docker Desktop abierto:

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps -a
```

Se espera que `db` esté **healthy**, `web` y `django` estén **Up**, y `migrate` pueda mostrar **Exited (0)** después de aplicar las migraciones.

Enlaces locales:

| Servicio | URL |
|---|---|
| Flask — restaurantes | http://localhost:5001/restaurantes |
| Flask — iniciar sesión | http://localhost:5001/login |
| Flask — mis pedidos | http://localhost:5001/mis-pedidos |
| Flask — cocina | http://localhost:5001/cocina |
| Flask — ver permisos del usuario | http://localhost:5001/auth/quien-soy |
| Django Admin | http://localhost:8001/admin/ |

Una instalación limpia no incluye necesariamente restaurantes ni platos de demostración. Se pueden cargar desde Django Admin después de crear un superusuario:

```powershell
docker compose exec django python manage.py createsuperuser
```

El superusuario de **Django Admin es independiente** de los usuarios y roles de Auth0.

Para detener los servicios sin eliminar el volumen de PostgreSQL:

```powershell
docker compose down
```

No utilizar `docker compose down -v` si se quieren conservar los datos.

## Configuración de Auth0 para evaluación

**Importante:** clonar GitHub y ejecutar Docker no crea automáticamente las cuentas de Auth0. Los usuarios, roles y permisos están almacenados en el tenant de Auth0, fuera del repositorio.

### 1. Configurar la aplicación y la API

En [Auth0 Dashboard](https://manage.auth0.com/):

1. En **Applications → Applications**, seleccionar o crear una aplicación de tipo **Regular Web Application**.
2. Copiar su `Client ID`, `Client Secret` y dominio del tenant al archivo `.env`.
3. En **Applications → APIs**, utilizar una API cuyo **Identifier** coincida exactamente con `AUTH0_AUDIENCE`.
4. En la configuración de la API, habilitar **RBAC** y **Add Permissions in the Access Token**.

### 2. Registrar URLs de localhost

Dentro de **Applications → Applications → [aplicación] → Settings → Application URIs**, configurar:

| Campo de Auth0 | Valor local |
|---|---|
| **Allowed Callback URLs** | `http://localhost:5001/auth/callback` |
| **Allowed Logout URLs** | `http://localhost:5001/` |
| **Allowed Web Origins** | `http://localhost:5001` |

Guardar con **Save Changes**. Si se usa la misma aplicación para producción, mantener también sus URLs HTTPS; no es necesario borrar las URLs de localhost.

### 3. Configurar roles y usuarios de prueba

En **User Management → Roles**, crear los siguientes roles y asignarles los permisos de la API:

| Rol | Permisos requeridos | Prueba sugerida |
|---|---|---|
| `cliente` | `create:pedidos`, `read:mis-pedidos` | Crear un pedido y consultar sus pedidos. |
| `cocina` | `read:pedidos`, `update:pedidos` | Ver la cola y avanzar un pedido. |
| `admin` | `read:pedidos`, `write:carta`, `delete:carta` | Gestionar restaurantes y platos desde Flask. |

En **User Management → Users**, crear o utilizar tres **cuentas de prueba** y asignarles el rol correspondiente desde la pestaña **Roles**.

Si el evaluador utiliza el tenant Auth0 del autor, necesita recibir **por un canal privado** la configuración `.env` de evaluación y las credenciales temporales de las cuentas de prueba. Si utiliza su propio tenant, debe crear la aplicación, la API y los roles anteriores.

**Nunca publicar contraseñas, Client Secrets, archivos `.env` ni credenciales de cuentas personales en este README o en GitHub.**

### 4. Verificar inicio de sesión y permisos

1. Abrir `http://localhost:5001/restaurantes`.
2. Entrar a `http://localhost:5001/login` e iniciar sesión con un usuario de prueba.
3. Visitar `http://localhost:5001/auth/quien-soy` para comprobar los permisos presentes en su token.
4. Como `cliente`, crear un pedido y consultarlo en `/mis-pedidos`.
5. Como `cocina`, entrar a `/cocina` y avanzar el estado de un pedido.
6. Como `admin`, utilizar `/restaurantes/crear` para administrar la carta.

Cerrar sesión desde el botón de la interfaz. La ruta `/auth/logout` acepta el método **POST**, por lo que abrirla directamente en una pestaña mediante GET puede producir **405 Method Not Allowed**.

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
- Un despliegue público **persistente** en EC2 con Nginx, dos subdominios y HTTPS.

Durante el desarrollo se comprobó el despliegue HTTPS en un laboratorio temporal de AWS Academy; sin embargo, dicho laboratorio elimina recursos al finalizar la sesión y no se garantiza que el servicio público permanezca activo. No se declara cobertura de pruebas que todavía no se haya demostrado.

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
