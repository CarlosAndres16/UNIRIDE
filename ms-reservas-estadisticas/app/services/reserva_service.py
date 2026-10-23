"""Consulta de reservas previa autorizacion del propietario del viaje."""

import logging
from typing import Annotated

from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.clients.http_client import resolverCorrelationId
from app.clients.viajes_client import ViajesClient, getViajesClient
from app.exceptions.exceptions import (
    ErrorInterno,
    RecursoNoEncontradoError,
    ServicioDependienteNoDisponibleError,
    SolicitudInvalidaError,
)
from app.models.reserva import EstadoReserva
from app.repositories.reserva_repository import (
    ReservaRepository,
    ResumenReservas,
    getReservaRepository,
)
from app.schemas.error_schema import CodigoError
from app.schemas.integracion_schema import EstadoViaje, ViajeExterno
from app.schemas.reserva_schema import ReservaSchema, ReservasViajeSchema
from app.security.jwt_service import ConductorAutenticado, verificarPropietario
from app.services.ocupacion_service import sincronizarOcupacion

logger = logging.getLogger("uniride.services.reservas")


def _validarIdentificador(value: int, campo: str) -> None:
    if type(value) is not int or value <= 0:
        raise SolicitudInvalidaError(
            "El identificador debe ser un entero positivo.",
            detalles=[{"campo": campo, "problema": "Debe ser un entero mayor que cero."}],
        )


def _errorPersistencia(correlationId: str) -> ErrorInterno:
    # No registrar la excepcion: puede contener SQL o datos privados.
    logger.error(
        "No se pudieron consultar o validar las reservas.",
        extra={"correlationId": correlationId},
    )
    return ErrorInterno()


class ReservaService:
    def __init__(
        self, repository: ReservaRepository, viajesClient: ViajesClient
    ) -> None:
        self._repository = repository
        self._viajesClient = viajesClient

    async def listarPorViaje(
        self,
        viajeId: int,
        conductor: ConductorAutenticado,
        estado: EstadoReserva | None = None,
        correlationId: str | None = None,
    ) -> ReservasViajeSchema:
        _validarIdentificador(viajeId, "viajeId")
        if estado is not None and not isinstance(estado, EstadoReserva):
            raise SolicitudInvalidaError(
                "El estado de reserva no es valido.",
                detalles=[
                    {
                        "campo": "estado",
                        "problema": "Debe ser PENDIENTE, CONFIRMADA o CANCELADA.",
                    }
                ],
            )

        correlationId = resolverCorrelationId(correlationId)
        # Ninguna lectura del repositorio ocurre antes de comprobar el viaje.
        viaje = await self._obtenerViajeAutorizado(viajeId, conductor, correlationId)

        def consultarReservas() -> tuple[ReservasViajeSchema, ResumenReservas]:
            # La lectura pyodbc y cualquier acceso de Pydantic a atributos ORM
            # se completan en el mismo trabajo fuera del event loop.
            try:
                reservas = self._repository.listarPorViaje(viajeId, estado)
                datos = [ReservaSchema.model_validate(reserva) for reserva in reservas]
                respuesta = ReservasViajeSchema(
                    viajeId=viajeId, total=len(datos), datos=datos
                )
                # El filtro de la lista nunca modifica el total confirmado que
                # se comunica a Viajes, aunque se consulten solo cancelaciones.
                resumen = self._repository.resumirPorViajes([viajeId])[viajeId]
                return respuesta, resumen
            except (SQLAlchemyError, ValidationError, ValueError):
                raise _errorPersistencia(correlationId) from None

        respuesta, resumen = await run_in_threadpool(consultarReservas)
        if viaje.estado == EstadoViaje.ACTIVO:
            await sincronizarOcupacion(
                viaje, resumen.pasajerosConfirmados, self._viajesClient, correlationId
            )
        return respuesta

    async def obtenerPorId(
        self,
        reservaId: int,
        conductor: ConductorAutenticado,
        correlationId: str | None = None,
    ) -> ReservaSchema:
        _validarIdentificador(reservaId, "reservaId")
        correlationId = resolverCorrelationId(correlationId)

        def consultarReserva() -> ReservaSchema | None:
            try:
                reserva = self._repository.obtenerPorId(reservaId)
                if reserva is None:
                    return None
                datos = ReservaSchema.model_validate(reserva)
                if datos.reservaId != reservaId:
                    raise ValueError("La reserva no corresponde al identificador solicitado.")
                return datos
            except (SQLAlchemyError, ValidationError, ValueError):
                raise _errorPersistencia(correlationId) from None

        # El registro se conserva internamente: no se devuelve ni se registra
        # ningun dato de pasajero antes de autorizar al propietario del viaje.
        reserva = await run_in_threadpool(consultarReserva)
        if reserva is None:
            raise RecursoNoEncontradoError(
                CodigoError.RESERVA_NO_ENCONTRADA,
                f"No existe una reserva con id {reservaId}.",
            )
        viaje = await self._obtenerViajeAutorizado(
            reserva.viajeId, conductor, correlationId
        )

        if viaje.estado == EstadoViaje.ACTIVO:
            def consultarResumen() -> ResumenReservas:
                try:
                    return self._repository.resumirPorViajes([reserva.viajeId])[
                        reserva.viajeId
                    ]
                except (SQLAlchemyError, ValidationError, ValueError):
                    raise _errorPersistencia(correlationId) from None

            resumen = await run_in_threadpool(consultarResumen)
            await sincronizarOcupacion(
                viaje, resumen.pasajerosConfirmados, self._viajesClient, correlationId
            )
        return reserva

    async def _obtenerViajeAutorizado(
        self,
        viajeId: int,
        conductor: ConductorAutenticado,
        correlationId: str,
    ) -> ViajeExterno:
        viaje = await self._viajesClient.obtenerViaje(viajeId, conductor, correlationId)
        if type(viaje.viajeId) is not int or viaje.viajeId != viajeId:
            logger.warning(
                "Viajes devolvio un identificador inesperado para viajeId=%s.",
                viajeId,
                extra={"correlationId": correlationId},
            )
            raise ServicioDependienteNoDisponibleError(
                "El servicio Viajes devolvio una respuesta tecnicamente invalida."
            )
        verificarPropietario(viaje.conductorId, conductor)
        return viaje


def getReservaService(
    repository: Annotated[ReservaRepository, Depends(getReservaRepository)],
    viajesClient: Annotated[ViajesClient, Depends(getViajesClient)],
) -> ReservaService:
    return ReservaService(repository, viajesClient)
