# SeizeMB API

API del e-commerce de SeizeMB: catálogo, carrito, pedidos por encargo y
reportes de ventas. FastAPI + SQLAlchemy + PostgreSQL.

No hay inventario. Los productos se piden a demanda: no se cargan 999
unidades ni se reserva stock. Un producto `in_stock` se puede pedir en
cualquier cantidad; apagarlo es dejar de ofrecerlo.

El pago activo es **contra entrega** (efectivo o Nequi) con confirmación
de las dos partes. Wompi queda en el backend pero **no se usa**.

## Arrancar en local

Necesitas Python 3.10+ y una base PostgreSQL.

```bash
git clone <url-del-repo>
cd SeizeMB

python -m venv .venv
.venv\Scripts\activate          # Linux/mac: source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env            # y llena DATABASE_URL y SECRET_KEY
```

Una base local rápida, si no quieres usar la de Supabase:

```bash
docker run -d --name seizemb-db \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=seizemb \
  -p 5432:5432 postgres:16-alpine
```

Crear el esquema y levantar la API:

```bash
alembic upgrade head
uvicorn app.main_app:app --reload
```

Documentación interactiva: <http://localhost:8000/docs>.

> El `main.py` de la raíz **no** levanta la API: solo crea las tablas con
> `create_all` en una base vacía. Para el día a día usa Alembic.

## Variables de entorno

Todas se leen en `app/core/config.py` y están explicadas en
[`.env.example`](.env.example). Las únicas obligatorias son
`DATABASE_URL` y `SECRET_KEY`. El resto (Google, Supabase, Wompi) se
puede dejar vacío: esos flujos quedan apagados.

En Render se cargan en Environment (no hay archivo `.env` allá).

## Migraciones (Alembic)

El esquema se versiona en `alembic/versions/`. **Nunca** se cambia la base
a mano ni con `create_all`.

```bash
alembic upgrade head                              # aplicar lo pendiente
alembic revision --autogenerate -m "que cambió"   # tras tocar un modelo
alembic downgrade -1                              # deshacer la última
alembic current                                   # en qué versión está
```

Alembic lee `DATABASE_URL` del entorno (no hay credenciales en
`alembic.ini`), así que apunta a la misma base que la app.

## Tests

```bash
pytest
```

Corren contra SQLite en memoria, así que no necesitan base ni Docker.
Para correrlos contra Postgres de verdad:

```bash
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/seizemb_test pytest
```

Linter (la misma versión que corre en CI):

```bash
ruff check .        # revisar
ruff check --fix .  # arreglar lo automático
```

CI (`.github/workflows/ci.yml`) corre en cada PR: `ruff`, `pytest` en
Python 3.10 y 3.12, y las migraciones contra un Postgres real.

## Crear un administrador

No hay endpoint para volverse admin (sería un agujero de seguridad). Se
hace por consola; si el email ya existe, lo promueve en vez de duplicarlo:

```bash
python -m app.scripts.create_admin admin@seizemb.com "Nombre Admin" "contraseña-segura"
```

En Render: Dashboard → el servicio → pestaña **Shell** → el mismo comando.

## Cómo está organizado

```
app/
├── api/v1/        endpoints (HTTP: validar entrada, códigos de estado)
├── services/      reglas de negocio (pedidos, auth, ventas)
├── repositories/  acceso a datos (queries, sin reglas de negocio)
├── models/        tablas SQLAlchemy
├── schemas/       entrada/salida Pydantic
├── core/          config, seguridad, headers, rate limit, storage
└── db/            engine, sesión y Base declarativa
alembic/           migraciones
tests/             pytest
```

La dependencia va siempre en un sentido: `api → services → repositories →
models`. Un repositorio nunca llama a un service.

### Endpoints

| Grupo | Ruta base | Qué hace |
|---|---|---|
| auth | `/api/v1/auth` | registro, login, Google, refresh, logout, perfil |
| products | `/api/v1/products` | catálogo público; crear/editar/imágenes es solo-admin |
| categories | `/api/v1/categories` | listar (público) y crear (admin) |
| cart | `/api/v1/cart` | carrito del usuario autenticado |
| orders | `/api/v1/orders` | checkout contra entrega, cancelar, entregas |
| webhooks | `/api/v1/webhooks/wompi` | Wompi (oculto; no se usa) |
| sales | `/api/v1/sales` | reportes de ventas (solo-admin) |

### Imágenes de producto

Cada producto puede tener **de 0 a 4** imágenes por color (ninguna es
obligatoria). Viven en la tabla `product_images` y se suben a Supabase
Storage; solo el admin puede tocarlas.

En la respuesta, `images` viene ordenada por `position` y `image_url` es
la primera de la lista (la principal).

## Cómo funciona la autenticación

- El **access token** (JWT, 15 min) va en `Authorization: Bearer ...`.
- El **refresh token** (30 días) va en una cookie `httpOnly`, con
  `Path=/api/v1/auth`; nunca se devuelve en el body. En la base solo se
  guarda su SHA-256.
- `POST /auth/refresh` **rota** el token: revoca el anterior y entrega uno
  nuevo. Si alguien reusa un token ya rotado, se asume robo y se revocan
  **todas** las sesiones de ese usuario.
- Admin es simplemente `is_admin` en la tabla `users`.
- `/auth/refresh` y `/auth/logout` exigen que el `Origin` sea uno de los
  dominios conocidos.

El frontend tiene que llamar con `credentials: "include"` para que la
cookie viaje; los orígenes permitidos están en `app/core/cors.py` y se
amplían con `FRONTEND_ORIGINS`.

### Rate limit

100 requests/minuto por IP en general, y más estricto en login, registro
y checkout. Dos cosas que hay que configurar bien al desplegar:

- `TRUSTED_PROXY_HOPS=1` en Render. Sin esto la app ve la IP del proxy y
  **todos los usuarios comparten el mismo cupo**.
- `RATE_LIMIT_STORAGE_URI` apuntando a un Redis si corres más de una
  instancia; en memoria cada una cuenta por su lado.

## Pedidos y pago contra entrega

1. `POST /orders/checkout` congela el carrito en un pedido `CONFIRMED`
   (efectivo o Nequi). No reserva inventario.
2. La dueña marca `IN_TRANSIT` cuando sale a entregar.
3. La dueña marca `AWAITING_CONFIRMATION` cuando entregó y le pagaron.
   Ahí se anota `paid_at` (recién acá la plata existe).
4. La clienta confirma con `PATCH /orders/{id}/confirm-delivery` y el
   pedido queda `DELIVERED` con `closed_by=CUSTOMER`.
5. Si la clienta nunca confirma, la dueña puede cerrarlo ella
   (`closed_by=SELLER`).

Un pedido `PENDING` de Wompi (si se reactivara) expira a las 2 horas.
Contra entrega no expira. Hay un tope de 3 pedidos contra entrega
abiertos por persona.

Los precios y costos se congelan en cada `OrderItem`, así que cambiar el
precio de un producto no altera las ventas ya hechas.

## Despliegue

Va en Render, con el `render.yaml` de la raíz: en Render se entra por
New → Blueprint, se conecta el repo y de ahí lee el archivo. Las
variables marcadas `sync: false` **no** viajan en el archivo (son
secretas): quedan vacías y se llenan a mano en Environment.

El blueprint arranca con:

```bash
alembic upgrade head && uvicorn app.main_app:app --host 0.0.0.0 --port $PORT
```

También hay un `Dockerfile`:

```bash
docker build -t seizemb-api .
docker run --rm -p 8000:8000 --env-file .env seizemb-api
```
