"""Cliente REST de Viajes, sin acceso a su base de datos."""

from collections.abc import AsyncIterator
from datetime import date
import logging
from typing import Annotated

from fastapi import Depends
import httpx
from pydantic import SecretStr, ValidationError

from app.clients.http_client import (
    ClienteHttp,
    getHttpClientSettingsSeguro,
    headersConductor,
    headersServicio,
    resolverCorrelationId,
)
from app.config.settings import HttpClientSettings, getServiceAuthSettings
from app.exceptions.exceptions import (
    ErrorInterno,
    ServicioDependienteNoDisponibleError,
    SolicitudInvalidaError,
)
from app.schemas.integracion_schema import (
    EstadoViaje,
    ListaViajesExterna,
    OcupacionExterna,
    ViajeExterno,
)
from app.security.jwt_service import ConductorAutenticado, verificarPropietario

logger = logging.getLogger("uniride.clients.viajes")
TAMANO_PAGINA = 50


def _validarEnteroPositivo(value: int, campo: str) -> None:
    if type(value) is not int or value <= 0:
        raise SolicitudInvalidaError(
            "Los identificadores y la pagina deben ser enteros positivos.",
            detalles=[{"campo": campo, "problema": "Debe ser un entero mayor que cero."}],
        )


def _parametrosListado(
    conductorId: int | None,
    vehiculoId: int | None,
    desde: date | None,
    hasta: date | None,
    pagina: int,
) -> dict[str, str | int]:
    for campo, value in (("conductorId", conductorId), ("vehiculoId", vehiculoId)):
        if value is not None:
            _validarEnteroPositivo(value, campo)
    _validarEnteroPositivo(pagina, "pagina")

    for campo, value in (("desde", desde), ("hasta", hasta)):
        if value is not None and type(value) is not date:
            raise SolicitudInvalidaError(
                "Los limites del periodo deben ser fechas.",
                detalles=[{"campo": campo, "problema": "Debe proporcionarse una fecha."}],
            )
    if desde is not None and hasta is not None and desde > hasta:
        raise SolicitudInvalidaError(
            "El inicio del periodo no puede ser posterior al final.",
            detalles=[{"campo": "desde", "problema": "No puede ser posterior a hasta."}],
        )

    params: dict[str, str | int] = {
        "estado": "TODOS",
        "pagina": pagina,
        "tamano": TAMANO_PAGINA,
    }
    if conductorId is not None:
        params["conductorId"] = conductorId
    if vehiculoId is not None:
        params["vehiculoId"] = vehiculoId
    if desde is not None:
        params["desde"] = desde.isoformat()
    if hasta is not None:
        params["hasta"] = hasta.isoformat()
    return params


def _respuestaInvalida(correlationId: str) -> ServicioDependienteNoDisponibleError:
    logger.warning(
        "Respuesta de Viajes inconsistente.", extra={"correlationId": correlationId}
    )
    return ServicioDependienteNoDisponibleError(
        "El servicio Viajes devolvio una respuesta tecnicamente invalida."
    )


class ViajesClient:
    """Propaga JWT o clave interna segun el endpoint y valida el contrato."""

    def __init__(
        self,
        settings: HttpClientSettings,
        httpClient: httpx.AsyncClient,
        serviceApiKey: SecretStr | None = None,
    ) -> None:
        self._cliente = ClienteHttp(
            settings, httpClient, str(settings.viajesServiceUrl), "Viajes"
        )
        self._serviceApiKey = serviceApiKey

    async def obtenerViaje(
        self,
        viajeId: int,
        conductor: ConductorAutenticado,
        correlationId: str | None = None,
    ) -> ViajeExterno:
        _validarEnteroPositivo(viajeId, "viajeId")
        headers = headersConductor(conductor, correlationId)
        viaje = await self._cliente.solicitar(
            "GET",
            f"/api/v1/viajes/{viajeId}",
            ViajeExterno,
            headers=headers,
        )
        if viaje.viajeId != viajeId:
            raise _respuestaInvalida(headers["X-Correlation-Id"])
        verificarPropietario(viaje.conductorId, conductor)
        return viaje

    async def listarViajes(
        self,
        conductor: ConductorAutenticado,
        *,
        conductorId: int | None = None,
        vehiculoId: int | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        pagina: int = 1,
        correlationId: str | None = None,
    ) -> ListaViajesExterna:
        params = _parametrosListado(conductorId, vehiculoId, desde, hasta, pagina)
        headers = headersConductor(conductor, correlationId)
        respuesta = await self._cliente.solicitar(
            "GET", "/api/v1/viajes", ListaViajesExterna, headers=headers, params=params
        )
        paginacion = respuesta.paginacion
        totalEsperadoPaginas = (
            paginacion.totalElementos + TAMANO_PAGINA - 1
        ) // TAMANO_PAGINA
        cantidadEsperada = (
            min(
                TAMANO_PAGINA,
                paginacion.totalElementos - (pagina - 1) * TAMANO_PAGINA,
            )
            if pagina <= totalEsperadoPaginas
            else 0
        )
        if (
            paginacion.pagina != pagina
            or paginacion.tamano != TAMANO_PAGINA
            or paginacion.totalPaginas != totalEsperadoPaginas
            or len(respuesta.datos) != cantidadEsperada
            or len({viaje.viajeId for viaje in respuesta.datos}) != len(respuesta.datos)
        ):
            raise _respuestaInvalida(headers["X-Correlation-Id"])
        for viaje in respuesta.datos:
            if (
                (conductorId is not None and viaje.conductorId != conductorId)
                or (vehiculoId is not None and viaje.vehiculoId != vehiculoId)
                or (desde is not None and viaje.fechaSalida < desde)
                or (hasta is not None and viaje.fechaSalida > hasta)
            ):
                raise _respuestaInvalida(headers["X-Correlation-Id"])
        return respuesta

    async def listarTodosLosViajes(
        self,
        conductor: ConductorAutenticado,
        *,
        conductorId: int | None = None,
        vehiculoId: int | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        correlationId: str | None = None,
    ) -> list[ViajeExterno]:
        # Validar antes de resolver el contexto o iniciar cualquier llamada.
        _parametrosListado(conductorId, vehiculoId, desde, hasta, 1)
        correlationId = resolverCorrelationId(correlationId)
        primera = await self.listarViajes(
            conductor,
            conductorId=conductorId,
            vehiculoId=vehiculoId,
            desde=desde,
            hasta=hasta,
            pagina=1,
            correlationId=correlationId,
        )
        referencia = primera.paginacion
        viajes = list(primera.datos)
        identificadores = {viaje.viajeId for viaje in viajes}

        for pagina in range(2, referencia.totalPaginas + 1):
            respuesta = await self.listarViajes(
                conductor,
                conductorId=conductorId,
                vehiculoId=vehiculoId,
                desde=desde,
                hasta=hasta,
                pagina=pagina,
                correlationId=correlationId,
            )
            actual = respuesta.paginacion
            if (
                actual.tamano != referencia.tamano
                or actual.totalElementos != referencia.totalElementos
                or actual.totalPaginas != referencia.totalPaginas
            ):
                raise _respuestaInvalida(correlationId)
            for viaje in respuesta.datos:
                if viaje.viajeId in identificadores:
                    raise _respuestaInvalida(correlationId)
                identificadores.add(viaje.viajeId)
                viajes.append(viaje)

        if len(viajes) != referencia.totalElementos:
            raise _respuestaInvalida(correlationId)
        # CANCELADO se conserva; su exclusion corresponde al calculo estadistico.
        return viajes

    async def actualizarOcupacion(
        self,
        viajeId: int,
        cuposOcupados: int,
        correlationId: str | None = None,
    ) -> OcupacionExterna:
        _validarEnteroPositivo(viajeId, "viajeId")
        if type(cuposOcupados) is not int or cuposOcupados < 0:
            raise SolicitudInvalidaError(
                "Los cupos ocupados deben ser un entero mayor o igual a cero.",
                detalles=[
                    {
                        "campo": "cuposOcupados",
                        "problema": "Debe ser un entero mayor o igual a cero.",
                    }
                ],
            )
        correlationId = resolverCorrelationId(correlationId)
        try:
            key = self._serviceApiKey
            if key is None:
                key = getServiceAuthSettings().serviceApiKey
            if not isinstance(key, SecretStr) or not key.get_secret_value().strip():
                raise ValueError("Clave interna no configurada.")
        except (ValidationError, ValueError):
            logger.error(
                "No se pudo cargar la configuracion de autenticacion interna.",
                extra={"correlationId": correlationId},
            )
            raise ErrorInterno() from None

        headers = headersServicio(key, correlationId)
        respuesta = await self._cliente.solicitar(
            "PUT",
            f"/api/v1/viajes/{viajeId}/ocupacion",
            OcupacionExterna,
            headers=headers,
            json={"cuposOcupados": cuposOcupados},
        )
        if (
            respuesta.viajeId != viajeId
            or respuesta.cuposDisponibles != respuesta.capacidad - cuposOcupados
            or respuesta.estado != EstadoViaje.ACTIVO
        ):
            raise _respuestaInvalida(headers["X-Correlation-Id"])
        return respuesta


async def getViajesClient(
    settings: Annotated[HttpClientSettings, Depends(getHttpClientSettingsSeguro)],
) -> AsyncIterator[ViajesClient]:
    """Mantiene y cierra una sesion HTTP durante la dependencia de FastAPI."""

    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as httpClient:
        yield ViajesClient(settings, httpClient)
