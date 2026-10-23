"""Consultas de reservas de los viajes del conductor autenticado."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from app.exceptions.handlers import getRequestCorrelationId
from app.models.reserva import EstadoReserva
from app.schemas.error_schema import ErrorResponse
from app.schemas.reserva_schema import ReservaSchema, ReservasViajeSchema
from app.security.jwt_service import ConductorAutenticado, getConductorAutenticado
from app.services.reserva_service import ReservaService, getReservaService

router = APIRouter(prefix="/api/v1/reservas", tags=["Reservas"])


@router.get(
    "/viaje/{viajeId}",
    response_model=ReservasViajeSchema,
    response_model_by_alias=False,
    summary="Consultar reservas de un viaje propio",
    responses={
        **{status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 500, 503)},
        "default": {"model": ErrorResponse, "description": "Error del servicio."},
    },
)
async def listarReservasPorViaje(
    request: Request,
    conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
    viajeId: Annotated[int, Path(gt=0)],
    service: Annotated[ReservaService, Depends(getReservaService)],
    estado: Annotated[EstadoReserva | None, Query()] = None,
) -> ReservasViajeSchema:
    return await service.listarPorViaje(
        viajeId, conductor, estado=estado,
        correlationId=getRequestCorrelationId(request),
    )


@router.get(
    "/{reservaId}",
    response_model=ReservaSchema,
    response_model_by_alias=False,
    summary="Consultar una reserva de un viaje propio",
    responses={
        **{status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 500, 503)},
        "default": {"model": ErrorResponse, "description": "Error del servicio."},
    },
)
async def obtenerReserva(
    request: Request,
    conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
    reservaId: Annotated[int, Path(gt=0)],
    service: Annotated[ReservaService, Depends(getReservaService)],
) -> ReservaSchema:
    return await service.obtenerPorId(
        reservaId, conductor, correlationId=getRequestCorrelationId(request)
    )
