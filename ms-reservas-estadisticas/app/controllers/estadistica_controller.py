"""Consultas autenticadas de estadisticas calculadas al solicitarse."""

from datetime import date
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BeforeValidator

from app.exceptions.handlers import getRequestCorrelationId
from app.schemas.error_schema import ErrorResponse
from app.schemas.estadistica_schema import (
    EstadisticaConductorSchema,
    EstadisticaVehiculoSchema,
    EstadisticaViajeSchema,
)
from app.security.jwt_service import ConductorAutenticado, getConductorAutenticado
from app.services.estadistica_service import EstadisticaService, getEstadisticaService

router = APIRouter(prefix="/api/v1/estadisticas", tags=["Estadisticas"])

RESPUESTAS_ERROR = {
    **{status: {"model": ErrorResponse} for status in (400, 401, 403, 404, 500, 503)},
    "default": {"model": ErrorResponse, "description": "Error del servicio."},
}


def validarFechaPeriodo(value):
    """Rechaza timestamps y datetime en los limites de fecha del contrato."""
    if value is None or type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("La fecha debe usar exclusivamente YYYY-MM-DD.")
    return value


@router.get(
    "/viaje/{viajeId}",
    response_model=EstadisticaViajeSchema,
    summary="Consultar estadisticas de un viaje propio",
    responses=RESPUESTAS_ERROR,
)
async def obtenerEstadisticaPorViaje(
    request: Request,
    conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
    viajeId: Annotated[int, Path(gt=0)],
    service: Annotated[EstadisticaService, Depends(getEstadisticaService)],
) -> EstadisticaViajeSchema:
    return await service.obtenerPorViaje(
        viajeId, conductor, correlationId=getRequestCorrelationId(request),
    )


@router.get(
    "/conductor/{conductorId}",
    response_model=EstadisticaConductorSchema,
    summary="Consultar estadisticas del conductor autenticado",
    responses=RESPUESTAS_ERROR,
)
async def obtenerEstadisticaPorConductor(
    request: Request,
    conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
    conductorId: Annotated[int, Path(gt=0)],
    service: Annotated[EstadisticaService, Depends(getEstadisticaService)],
    desde: Annotated[date | None, BeforeValidator(validarFechaPeriodo), Query(description="Fecha inicial inclusiva, YYYY-MM-DD.")] = None,
    hasta: Annotated[date | None, BeforeValidator(validarFechaPeriodo), Query(description="Fecha final inclusiva, YYYY-MM-DD.")] = None,
) -> EstadisticaConductorSchema:
    return await service.obtenerPorConductor(
        conductorId, conductor, desde=desde, hasta=hasta,
        correlationId=getRequestCorrelationId(request),
    )


@router.get(
    "/vehiculo/{vehiculoId}",
    response_model=EstadisticaVehiculoSchema,
    summary="Consultar estadisticas de un vehiculo propio",
    responses=RESPUESTAS_ERROR,
)
async def obtenerEstadisticaPorVehiculo(
    request: Request,
    conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
    vehiculoId: Annotated[int, Path(gt=0)],
    service: Annotated[EstadisticaService, Depends(getEstadisticaService)],
    desde: Annotated[date | None, BeforeValidator(validarFechaPeriodo), Query(description="Fecha inicial inclusiva, YYYY-MM-DD.")] = None,
    hasta: Annotated[date | None, BeforeValidator(validarFechaPeriodo), Query(description="Fecha final inclusiva, YYYY-MM-DD.")] = None,
) -> EstadisticaVehiculoSchema:
    return await service.obtenerPorVehiculo(
        vehiculoId, conductor, desde=desde, hasta=hasta,
        correlationId=getRequestCorrelationId(request),
    )
