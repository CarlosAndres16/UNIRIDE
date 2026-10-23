from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import getAuthService, getConductorId, getConductorService
from app.schemas.auth_schema import LoginRequest, LoginResponse, RegistrarConductorRequest
from app.schemas.conductor_schema import ConductorResponse
from app.schemas.error_schema import ErrorResponse
from app.services.auth_service import AuthService
from app.services.conductor_service import ConductorService

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post(
    "/registro",
    status_code=status.HTTP_201_CREATED,
    response_model=ConductorResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Registrar un conductor",
)
def registrar(
    request: RegistrarConductorRequest,
    service: Annotated[AuthService, Depends(getAuthService)],
) -> ConductorResponse:
    return service.registrar(request)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
    summary="Validar credenciales y emitir un JWT",
)
def login(
    request: LoginRequest,
    service: Annotated[AuthService, Depends(getAuthService)],
) -> LoginResponse:
    return service.login(request)


@router.get(
    "/me",
    response_model=ConductorResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Consultar el conductor identificado por JWT.sub",
)
def consultarAutenticado(
    conductorId: Annotated[int, Depends(getConductorId)],
    service: Annotated[ConductorService, Depends(getConductorService)],
) -> ConductorResponse:
    return service.consultar(conductorId, conductorId)
