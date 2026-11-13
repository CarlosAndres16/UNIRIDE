"""Composición de dependencias (reemplazables en las pruebas)."""

from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.settings import Settings, getSettings
from app.exceptions.exceptions import AppException
from app.repositories.vehiculo_repository import VehiculoRepository
from app.security.jwt_service import JWTService
from app.services.vehiculo_service import VehiculoService

bearerScheme = HTTPBearer(auto_error=False, scheme_name="BearerJWT")


def getJwtService(settings: Annotated[Settings, Depends(getSettings)]) -> JWTService:
    return JWTService(settings)


def getRepository(settings: Annotated[Settings, Depends(getSettings)]) -> VehiculoRepository:
    return VehiculoRepository(settings)


def getVehiculoService(
    repository: Annotated[VehiculoRepository, Depends(getRepository)],
) -> VehiculoService:
    return VehiculoService(repository)


def getConductorId(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearerScheme)],
    jwtService: Annotated[JWTService, Depends(getJwtService)],
) -> int:
    """conductorId sale siempre del claim sub del JWT, nunca del cuerpo."""
    cabeceras = request.headers.getlist("authorization")
    partes = cabeceras[0].split() if len(cabeceras) == 1 else []
    if credentials is None or len(partes) != 2 or partes[0].lower() != "bearer":
        raise AppException(
            401, "NO_AUTENTICADO", "Se requiere un token Bearer válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return jwtService.validarToken(partes[1])
