"""Estadisticas calculadas al consultar, sin persistir resultados derivados."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import logging
from typing import Annotated

from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.clients.http_client import resolverCorrelationId
from app.clients.vehiculos_client import VehiculosClient, getVehiculosClient
from app.clients.viajes_client import ViajesClient, getViajesClient
from app.exceptions.exceptions import (
    ErrorInterno,
    ServicioDependienteNoDisponibleError,
    SolicitudInvalidaError,
)
from app.repositories.reserva_repository import (
    ReservaRepository,
    ResumenReservas,
    getReservaRepository,
)
from app.schemas.estadistica_schema import (
    EstadisticaConductorSchema,
    EstadisticaVehiculoSchema,
    EstadisticaViajeSchema,
    PeriodoSchema,
)
from app.schemas.integracion_schema import EstadoViaje, ViajeExterno
from app.security.jwt_service import ConductorAutenticado, verificarPropietario
from app.services.ocupacion_service import sincronizarOcupacion

logger = logging.getLogger("uniride.services.estadisticas")


def _validarIdentificador(value: int, campo: str) -> None:
    if type(value) is not int or value <= 0:
        raise SolicitudInvalidaError(
            "El identificador debe ser un entero positivo.",
            detalles=[{"campo": campo, "problema": "Debe ser un entero mayor que cero."}],
        )


def _periodo(desde: date | None, hasta: date | None) -> PeriodoSchema | None:
    for campo, value in (("desde", desde), ("hasta", hasta)):
        if value is not None and type(value) is not date:
            raise SolicitudInvalidaError(
                "Los limites del periodo deben ser fechas.",
                detalles=[{"campo": campo, "problema": "Debe usar YYYY-MM-DD."}],
            )
    if desde is not None and hasta is not None and desde > hasta:
        raise SolicitudInvalidaError(
            "El inicio del periodo no puede ser posterior al final.",
            detalles=[{"campo": "desde", "problema": "No puede ser posterior a hasta."}],
        )
    return None if desde is None and hasta is None else PeriodoSchema(desde=desde, hasta=hasta)


def _porcentaje(pasajeros: int, capacidad: int, correlationId: str) -> float:
    if capacidad == 0:
        logger.warning(
            "Ocupacion calculada con capacidad cero.",
            extra={"correlationId": correlationId},
        )
        return 0.0
    if pasajeros > capacidad:
        logger.warning(
            "La ocupacion confirmada supera la capacidad ofrecida.",
            extra={"correlationId": correlationId},
        )
    porcentaje = Decimal(pasajeros) * Decimal(100) / Decimal(capacidad)
    # Los contadores conservan los datos reales; el porcentaje respeta 0..100.
    limitado = min(Decimal(100), max(Decimal(0), porcentaje))
    return float(limitado.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _respuestaViajesInvalida(correlationId: str) -> ServicioDependienteNoDisponibleError:
    logger.warning(
        "Viajes devolvio datos inconsistentes para las estadisticas.",
        extra={"correlationId": correlationId},
    )
    return ServicioDependienteNoDisponibleError(
        "El servicio Viajes devolvio una respuesta tecnicamente invalida."
    )


class EstadisticaService:
    def __init__(
        self,
        repository: ReservaRepository,
        viajesClient: ViajesClient,
        vehiculosClient: VehiculosClient,
    ) -> None:
        self._repository = repository
        self._viajesClient = viajesClient
        self._vehiculosClient = vehiculosClient

    async def _leerResumenes(
        self, viajeIds: list[int], correlationId: str,
    ) -> dict[int, ResumenReservas]:
        if not viajeIds:
            return {}

        def consultar() -> dict[int, ResumenReservas]:
            try:
                resumenes = self._repository.resumirPorViajes(viajeIds)
                if set(resumenes) != set(viajeIds):
                    raise ValueError("Los resumenes no corresponden a los viajes.")
                for resumen in resumenes.values():
                    contadores = (
                        resumen.totalReservas,
                        resumen.reservasConfirmadas,
                        resumen.reservasCanceladas,
                        resumen.reservasPendientes,
                        resumen.pasajerosConfirmados,
                    )
                    if any(type(value) is not int or value < 0 for value in contadores):
                        raise ValueError("Los contadores de reservas no son validos.")
                    if (
                        resumen.totalReservas
                        != resumen.reservasConfirmadas + resumen.reservasCanceladas + resumen.reservasPendientes
                        or resumen.pasajerosConfirmados < resumen.reservasConfirmadas
                    ):
                        raise ValueError("Los contadores de reservas son inconsistentes.")
                return resumenes
            except (SQLAlchemyError, ValidationError, ValueError):
                logger.error(
                    "No se pudieron consultar o validar los resumenes de reservas.",
                    extra={"correlationId": correlationId},
                )
                raise ErrorInterno() from None

        return await run_in_threadpool(consultar)

    def _seleccionarViajes(
        self,
        viajes: list[ViajeExterno],
        conductor: ConductorAutenticado,
        desde: date | None,
        hasta: date | None,
        correlationId: str,
        vehiculoId: int | None = None,
    ) -> list[ViajeExterno]:
        seleccionados = []
        identificadores = set()
        for viaje in viajes:
            verificarPropietario(viaje.conductorId, conductor)
            if (
                type(viaje.viajeId) is not int
                or viaje.viajeId <= 0
                or viaje.viajeId in identificadores
                or (vehiculoId is not None and viaje.vehiculoId != vehiculoId)
                or (desde is not None and viaje.fechaSalida < desde)
                or (hasta is not None and viaje.fechaSalida > hasta)
                or viaje.estado not in (EstadoViaje.ACTIVO, EstadoViaje.FINALIZADO, EstadoViaje.CANCELADO)
            ):
                raise _respuestaViajesInvalida(correlationId)
            identificadores.add(viaje.viajeId)
            if viaje.estado != EstadoViaje.CANCELADO:
                seleccionados.append(viaje)
        return seleccionados

    async def _sincronizarViajes(
        self, viajes: list[ViajeExterno], resumenes: dict[int, ResumenReservas], correlationId: str,
    ) -> None:
        # Sin concurrencia sobre el cliente ni sobre la sesion SQL de la consulta.
        for viaje in viajes:
            if viaje.estado == EstadoViaje.ACTIVO:
                await sincronizarOcupacion(
                    viaje, resumenes[viaje.viajeId].pasajerosConfirmados,
                    self._viajesClient, correlationId,
                )

    async def obtenerPorViaje(
        self, viajeId: int, conductor: ConductorAutenticado, correlationId: str | None = None,
    ) -> EstadisticaViajeSchema:
        _validarIdentificador(viajeId, "viajeId")
        correlationId = resolverCorrelationId(correlationId)
        viaje = await self._viajesClient.obtenerViaje(viajeId, conductor, correlationId)
        if type(viaje.viajeId) is not int or viaje.viajeId != viajeId:
            raise _respuestaViajesInvalida(correlationId)
        verificarPropietario(viaje.conductorId, conductor)
        resumenes = await self._leerResumenes([viajeId], correlationId)
        resumen = resumenes[viajeId]
        respuesta = EstadisticaViajeSchema(
            viajeId=viajeId,
            vehiculoId=viaje.vehiculoId,
            cuposOfrecidos=viaje.capacidad,
            totalReservas=resumen.totalReservas,
            reservasConfirmadas=resumen.reservasConfirmadas,
            reservasCanceladas=resumen.reservasCanceladas,
            reservasPendientes=resumen.reservasPendientes,
            pasajerosConfirmados=resumen.pasajerosConfirmados,
            cuposDisponibles=max(0, viaje.capacidad - resumen.pasajerosConfirmados),
            porcentajeOcupacion=_porcentaje(resumen.pasajerosConfirmados, viaje.capacidad, correlationId),
        )
        await self._sincronizarViajes([viaje], resumenes, correlationId)
        return respuesta

    async def obtenerPorConductor(
        self,
        conductorId: int,
        conductor: ConductorAutenticado,
        desde: date | None = None,
        hasta: date | None = None,
        correlationId: str | None = None,
    ) -> EstadisticaConductorSchema:
        _validarIdentificador(conductorId, "conductorId")
        periodo = _periodo(desde, hasta)
        verificarPropietario(conductorId, conductor)
        correlationId = resolverCorrelationId(correlationId)
        viajes = await self._viajesClient.listarTodosLosViajes(
            conductor, conductorId=conductorId, desde=desde, hasta=hasta,
            correlationId=correlationId,
        )
        viajes = self._seleccionarViajes(viajes, conductor, desde, hasta, correlationId)
        resumenes = await self._leerResumenes([viaje.viajeId for viaje in viajes], correlationId)
        capacidad = sum(viaje.capacidad for viaje in viajes)
        pasajeros = sum(resumen.pasajerosConfirmados for resumen in resumenes.values())
        # El contrato no define ponderacion del promedio. Se usa la ocupacion
        # global: suma de pasajeros / suma de capacidades de los viajes incluidos.
        respuesta = EstadisticaConductorSchema(
            conductorId=conductorId,
            periodo=periodo,
            viajesConsultados=len(viajes),
            vehiculosUtilizados=len({viaje.vehiculoId for viaje in viajes}),
            totalReservas=sum(resumen.totalReservas for resumen in resumenes.values()),
            reservasConfirmadas=sum(resumen.reservasConfirmadas for resumen in resumenes.values()),
            reservasCanceladas=sum(resumen.reservasCanceladas for resumen in resumenes.values()),
            pasajerosConfirmados=pasajeros,
            porcentajeOcupacionPromedio=_porcentaje(pasajeros, capacidad, correlationId),
        )
        await self._sincronizarViajes(viajes, resumenes, correlationId)
        return respuesta

    async def obtenerPorVehiculo(
        self,
        vehiculoId: int,
        conductor: ConductorAutenticado,
        desde: date | None = None,
        hasta: date | None = None,
        correlationId: str | None = None,
    ) -> EstadisticaVehiculoSchema:
        _validarIdentificador(vehiculoId, "vehiculoId")
        periodo = _periodo(desde, hasta)
        correlationId = resolverCorrelationId(correlationId)
        vehiculo = await self._vehiculosClient.obtenerVehiculo(vehiculoId, conductor, correlationId)
        if type(vehiculo.vehiculoId) is not int or vehiculo.vehiculoId != vehiculoId:
            logger.warning(
                "Vehiculos devolvio un identificador inesperado.",
                extra={"correlationId": correlationId},
            )
            raise ServicioDependienteNoDisponibleError(
                "El servicio Vehiculos devolvio una respuesta tecnicamente invalida."
            )
        verificarPropietario(vehiculo.conductorId, conductor)
        viajes = await self._viajesClient.listarTodosLosViajes(
            conductor, conductorId=conductor.conductorId, vehiculoId=vehiculoId,
            desde=desde, hasta=hasta, correlationId=correlationId,
        )
        viajes = self._seleccionarViajes(viajes, conductor, desde, hasta, correlationId, vehiculoId)
        resumenes = await self._leerResumenes([viaje.viajeId for viaje in viajes], correlationId)
        capacidad = sum(viaje.capacidad for viaje in viajes)
        pasajeros = sum(resumen.pasajerosConfirmados for resumen in resumenes.values())
        # Mismo promedio ponderado por capacidad que en la consulta de conductor.
        respuesta = EstadisticaVehiculoSchema(
            vehiculoId=vehiculoId,
            conductorId=vehiculo.conductorId,
            periodo=periodo,
            viajesConsultados=len(viajes),
            totalReservas=sum(resumen.totalReservas for resumen in resumenes.values()),
            reservasConfirmadas=sum(resumen.reservasConfirmadas for resumen in resumenes.values()),
            reservasCanceladas=sum(resumen.reservasCanceladas for resumen in resumenes.values()),
            pasajerosConfirmados=pasajeros,
            cuposOfrecidosAcumulados=capacidad,
            porcentajeOcupacionPromedio=_porcentaje(pasajeros, capacidad, correlationId),
        )
        await self._sincronizarViajes(viajes, resumenes, correlationId)
        return respuesta


def getEstadisticaService(
    repository: Annotated[ReservaRepository, Depends(getReservaRepository)],
    viajesClient: Annotated[ViajesClient, Depends(getViajesClient)],
    vehiculosClient: Annotated[VehiculosClient, Depends(getVehiculosClient)],
) -> EstadisticaService:
    return EstadisticaService(repository, viajesClient, vehiculosClient)
