"""Composición de repositorios y servicios con dependencias reemplazables."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config.database import getSession
from app.config.settings import Settings, getSettings
from app.exceptions.exceptions import AppException
from app.repositories.conductor_repository import ConductorRepository
from app.security.jwt_service import JWTService
from app.security.password_service import PasswordService
from app.services.auth_service import AuthService
from app.services.conductor_service import ConductorService

bearerScheme = HTTPBearer(auto_error=False, scheme_name="BearerJWT")


@lru_cache(maxsize=1)
def getPasswordService() -> PasswordService:
    return PasswordService()


def getJwtService(settings: Annotated[Settings, Depends(getSettings)]) -> JWTService:
    return JWTService(settings)


def getRepository(session: Annotated[Session, Depends(getSession)]) -> ConductorRepository:
    return ConductorRepository(session)


def getAuthService(
    repository: Annotated[ConductorRepository, Depends(getRepository)],
    passwordService: Annotated[PasswordService, Depends(getPasswordService)],
    jwtService: Annotated[JWTService, Depends(getJwtService)],
) -> AuthService:
    return AuthService(repository, passwordService, jwtService)


def getConductorService(
    repository: Annotated[ConductorRepository, Depends(getRepository)],
) -> ConductorService:
    return ConductorService(repository)


def getConductorId(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearerScheme)],
    jwtService: Annotated[JWTService, Depends(getJwtService)],
) -> int:
    authHeaders = request.headers.getlist("authorization")
    parts = authHeaders[0].split() if len(authHeaders) == 1 else []
    if credentials is None or len(parts) != 2 or parts[0].lower() != "bearer":
        raise AppException(
            401,
            "NO_AUTENTICADO",
            "Se requiere un token Bearer válido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return jwtService.validarToken(parts[1])
