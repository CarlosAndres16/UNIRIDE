"""Consultas de solo lectura sobre las reservas propias del microservicio."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlalchemy import BigInteger, cast, func, select
from sqlalchemy.orm import Session

from app.config.database import getSession
from app.models.reserva import EstadoReserva, Reserva


@dataclass(frozen=True)
class ResumenReservas:
    totalReservas: int = 0
    reservasConfirmadas: int = 0
    reservasCanceladas: int = 0
    reservasPendientes: int = 0
    pasajerosConfirmados: int = 0


class ReservaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def listarPorViaje(
        self, viajeId: int, estado: EstadoReserva | None = None
    ) -> list[Reserva]:
        consulta = select(Reserva).where(Reserva.viajeId == viajeId)
        if estado is not None:
            consulta = consulta.where(Reserva.estado == estado.value)
        consulta = consulta.order_by(Reserva.id)
        return list(self._session.scalars(consulta).all())

    def obtenerPorId(self, reservaId: int) -> Reserva | None:
        consulta = select(Reserva).where(Reserva.id == reservaId)
        return self._session.scalars(consulta).one_or_none()

    def resumirPorViajes(self, viajeIds: list[int]) -> dict[int, ResumenReservas]:
        """Agrupa la base propia sin superar el limite de parametros de SQL Server."""

        if any(type(viajeId) is not int or viajeId <= 0 for viajeId in viajeIds):
            raise ValueError("Los identificadores del resumen deben ser enteros positivos.")
        identificadores = list(dict.fromkeys(viajeIds))
        resumenes = {viajeId: ResumenReservas() for viajeId in identificadores}
        for inicio in range(0, len(identificadores), 1000):
            lote = identificadores[inicio : inicio + 1000]
            consulta = (
                select(
                    Reserva.viajeId,
                    Reserva.estado,
                    func.count(Reserva.id).label("cantidad"),
                    func.sum(cast(Reserva.cuposReservados, BigInteger)).label("cupos"),
                )
                .where(Reserva.viajeId.in_(lote))
                .group_by(Reserva.viajeId, Reserva.estado)
            )
            for viajeId, estado, cantidad, cupos in self._session.execute(consulta).all():
                # Un estado inesperado es corrupcion de datos, no una reserva
                # que deba desaparecer silenciosamente de las estadisticas.
                estadoReserva = EstadoReserva(estado)
                if (
                    type(viajeId) is not int
                    or viajeId not in lote
                    or type(cantidad) is not int
                    or cantidad < 1
                    or type(cupos) is not int
                    or cupos < cantidad
                ):
                    raise ValueError("El agregado de reservas contiene datos invalidos.")
                anterior = resumenes[viajeId]
                resumenes[viajeId] = ResumenReservas(
                    totalReservas=anterior.totalReservas + cantidad,
                    reservasConfirmadas=anterior.reservasConfirmadas + (
                        cantidad if estadoReserva == EstadoReserva.CONFIRMADA else 0
                    ),
                    reservasCanceladas=anterior.reservasCanceladas + (
                        cantidad if estadoReserva == EstadoReserva.CANCELADA else 0
                    ),
                    reservasPendientes=anterior.reservasPendientes + (
                        cantidad if estadoReserva == EstadoReserva.PENDIENTE else 0
                    ),
                    pasajerosConfirmados=anterior.pasajerosConfirmados + (
                        cupos if estadoReserva == EstadoReserva.CONFIRMADA else 0
                    ),
                )
        return resumenes


def getReservaRepository(
    session: Annotated[Session, Depends(getSession)],
) -> ReservaRepository:
    """Construye el repositorio sin ejecutar consultas ni abrir conexiones."""

    return ReservaRepository(session)
