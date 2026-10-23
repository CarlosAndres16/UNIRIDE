from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.dependencies import getConductorId, getConductorService
from app.schemas.conductor_schema import ActualizarConductorRequest, ConductorResponse
from app.schemas.error_schema import ErrorResponse
from app.services.conductor_service import ConductorService

router = APIRouter(prefix="/api/v1/conductores", tags=["Conductores"])
ConductorIdPath = Annotated[int, Path(gt=0, le=2147483647)]
commonErrors = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


@router.get(
    "/{conductorId}",
    response_model=ConductorResponse,
    responses=commonErrors,
    summary="Consultar el recurso propio",
)
def consultar(
    conductorId: ConductorIdPath,
    conductorIdAutenticado: Annotated[int, Depends(getConductorId)],
    service: Annotated[ConductorService, Depends(getConductorService)],
) -> ConductorResponse:
    return service.consultar(conductorId, conductorIdAutenticado)


@router.put(
    "/{conductorId}",
    response_model=ConductorResponse,
    responses=commonErrors,
    summary="Reemplazar nombre y teléfono del conductor propio",
)
def actualizar(
    conductorId: ConductorIdPath,
    request: ActualizarConductorRequest,
    conductorIdAutenticado: Annotated[int, Depends(getConductorId)],
    service: Annotated[ConductorService, Depends(getConductorService)],
) -> ConductorResponse:
    return service.actualizar(conductorId, conductorIdAutenticado, request)
