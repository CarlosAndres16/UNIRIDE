# ms-vehiculos

Microservicio de Vehículos de UniRide. Cumple el **Contrato Técnico Unificado 1.0** (secciones 3, 4, 7, 11–15).

- Puerto: **8082** · Base de datos: PostgreSQL `unirride_vehiculos` · Python 3.12 + FastAPI
- No llama a ningún servicio. Valida el JWT (HS256, `JWT_SECRET`) y toma `conductorId` del claim `sub`.

## Variables de entorno (copia `.env.example` a `.env`)

`SERVER_PORT`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `JWT_SECRET` (mín. 32 caracteres, igual en los 4 servicios).

## Arranque con Docker

```bash
cp .env.example .env     # completa DB_PASSWORD y JWT_SECRET
docker compose up --build
```

Si ya tenías datos de la versión anterior, ejecuta `migracion_desde_version_anterior.sql` o `docker compose down -v` para empezar limpio.

## Arranque local sin Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app
```

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```

## Endpoints (todos exigen `Authorization: Bearer <JWT>`)

| Método | Ruta | Éxito | Errores |
|---|---|---|---|
| POST | `/api/v1/vehiculos` | 201 Vehículo `ACTIVO` | 400, 401, 403, 409 `PLACA_YA_REGISTRADA` |
| GET | `/api/v1/vehiculos` | 200 `{"datos":[…]}` (solo los del conductor) | 401 |
| GET | `/api/v1/vehiculos/{vehiculoId}` | 200 Vehículo | 400, 401, 403, 404 `VEHICULO_NO_ENCONTRADO` |
| PUT | `/api/v1/vehiculos/{vehiculoId}` | 200 Vehículo | 400, 401, 403, 404, 409 |
| DELETE | `/api/v1/vehiculos/{vehiculoId}` | 204 (baja lógica → `INACTIVO`) | 401, 403, 404 |

Además `/health` (sin token) para Docker; no es parte del contrato. Base de datos caída → 503 `SERVICIO_DEPENDIENTE_NO_DISPONIBLE`.
