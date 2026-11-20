"""Comprobaciones operativas públicas sin información de configuración privada."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config.database import getEngine


router = APIRouter(include_in_schema=False)
SERVICE_NAME = "ms-usuarios-auth"


@router.get("/health")
def health() -> dict[str, str]:
    # Liveness no depende del estado de SQL Server ni carga sus credenciales.
    return {"status": "UP", "servicio": SERVICE_NAME}


@router.get("/health/ready")
def readiness() -> JSONResponse:
    try:
        with getEngine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        # Ni la respuesta ni los logs incluyen errores del driver o credenciales.
        return JSONResponse(
            status_code=503,
            content={"status": "DOWN", "servicio": SERVICE_NAME, "database": "DOWN"},
        )
    return JSONResponse(
        content={"status": "UP", "servicio": SERVICE_NAME, "database": "UP"}
    )
