"""Cliente REST de Vehiculos con comprobacion defensiva del propietario."""

from collections.abc import AsyncIterator
import logging
from typing import Annotated

from fastapi import Depends
import httpx

from app.clients.http_client import (
    ClienteHttp,
    getHttpClientSettingsSeguro,
    headersConductor,
)
from app.config.settings import HttpClientSettings
from app.exceptions.exceptions import (
    ServicioDependienteNoDisponibleError,
    SolicitudInvalidaError,
)
from app.schemas.integracion_schema import VehiculoExterno
from app.security.jwt_service import ConductorAutenticado, verificarPropietario

logger = logging.getLogger("uniride.clients.vehiculos")


class VehiculosClient:
    def __init__(
        self, settings: HttpClientSettings, httpClient: httpx.AsyncClient
    ) -> None:
        self._cliente = ClienteHttp(
            settings, httpClient, str(settings.vehiculosServiceUrl), "Vehiculos"
        )

    async def obtenerVehiculo(
        self,
        vehiculoId: int,
        conductor: ConductorAutenticado,
        correlationId: str | None = None,
    ) -> VehiculoExterno:
        if type(vehiculoId) is not int or vehiculoId <= 0:
            raise SolicitudInvalidaError(
                "El identificador del vehiculo debe ser un entero positivo.",
                detalles=[
                    {"campo": "vehiculoId", "problema": "Debe ser un entero mayor que cero."}
                ],
            )
        headers = headersConductor(conductor, correlationId)
        vehiculo = await self._cliente.solicitar(
            "GET",
            f"/api/v1/vehiculos/{vehiculoId}",
            VehiculoExterno,
            headers=headers,
        )
        if vehiculo.vehiculoId != vehiculoId:
            logger.warning(
                "Respuesta de Vehiculos inconsistente.",
                extra={"correlationId": headers["X-Correlation-Id"]},
            )
            raise ServicioDependienteNoDisponibleError(
                "El servicio Vehiculos devolvio una respuesta tecnicamente invalida."
            )
        verificarPropietario(vehiculo.conductorId, conductor)
        return vehiculo


async def getVehiculosClient(
    settings: Annotated[HttpClientSettings, Depends(getHttpClientSettingsSeguro)],
) -> AsyncIterator[VehiculosClient]:
    """Cierra la sesion aunque falle la consulta o el codigo consumidor."""

    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as httpClient:
        yield VehiculosClient(settings, httpClient)
