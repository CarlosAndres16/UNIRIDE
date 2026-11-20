"""Diagnóstico sin autenticación: proceso y conexión a la base propietaria."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config.database import getEngine

router = APIRouter(tags=["Salud"])
SERVICIO = "ms-reservas-estadisticas"


@router.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "UP", "servicio": SERVICIO}


def databaseReady() -> bool:
    # FastAPI ejecuta la ruta síncrona en el pool de hilos, fuera del event loop.
    try:
        with getEngine().connect() as connection:
            return connection.execute(text("SELECT 1")).scalar_one() == 1
    except Exception:
        # No devuelve mensajes ODBC, nombres internos ni credenciales.
        return False


@router.get("/health/ready", include_in_schema=False)
def ready(available: bool = Depends(databaseReady)) -> JSONResponse:
    return JSONResponse(
        status_code=200 if available else 503,
        content={"status": "UP" if available else "DOWN", "servicio": SERVICIO,
                 "database": "UP" if available else "DOWN"},
    )
