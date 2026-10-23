"""Carga idempotente de las tres reservas de ejemplo en SQL Server."""

import sys
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import getEngine, getSessionFactory
from app.models import EstadoReserva, Reserva

BASE_DATOS_DESTINO = "unirride_reservas"

DATOS_PRUEBA = (
    {
        "viajeId": 305,
        "pasajeroNombre": "Laura Gómez",
        "cuposReservados": 1,
        "estado": EstadoReserva.CONFIRMADA,
        "fechaReserva": datetime(2026, 10, 1, 14, 20, tzinfo=UTC),
    },
    {
        "viajeId": 305,
        "pasajeroNombre": "David Ruiz",
        "cuposReservados": 1,
        "estado": EstadoReserva.CONFIRMADA,
        "fechaReserva": datetime(2026, 10, 1, 14, 21, tzinfo=UTC),
    },
    {
        "viajeId": 305,
        "pasajeroNombre": "Carlos Pérez",
        "cuposReservados": 1,
        "estado": EstadoReserva.CANCELADA,
        "fechaReserva": datetime(2026, 10, 1, 14, 22, tzinfo=UTC),
    },
)


class DestinoNoPermitidoError(Exception):
    """La conexión no corresponde a la base de datos propia del servicio."""


def cargarReservas(session: Session) -> tuple[int, int]:
    """Agrega ejemplos ausentes; la transacción la controla quien invoca.

    La identidad de cada ejemplo usa viaje, nombre y fecha UTC. Si ya existe,
    conserva sus cupos y estado actuales. Los hints mantienen los bloqueos de
    lectura y de rango hasta que finalice la transacción en SQL Server.
    """

    databaseName = session.scalar(select(func.DB_NAME()))
    if databaseName != BASE_DATOS_DESTINO:
        raise DestinoNoPermitidoError

    creadas = 0
    existentes = 0

    for datosReserva in DATOS_PRUEBA:
        consulta = (
            select(Reserva.id)
            .where(
                Reserva.viajeId == datosReserva["viajeId"],
                Reserva.pasajeroNombre == datosReserva["pasajeroNombre"],
                Reserva.fechaReserva == datosReserva["fechaReserva"],
            )
            .with_hint(Reserva, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
            .limit(1)
        )

        if session.scalar(consulta) is not None:
            existentes += 1
            continue

        session.add(Reserva(**datosReserva))
        creadas += 1

    return creadas, existentes


def main() -> int:
    """Carga las tres reservas en una única transacción y sin revelar secretos."""

    try:
        engine = getEngine()
        try:
            with getSessionFactory().begin() as session:
                creadas, existentes = cargarReservas(session)
        finally:
            engine.dispose()
    except DestinoNoPermitidoError:
        print(
            "Carga cancelada: el destino debe ser la base unirride_reservas. Revisa DB_NAME.",
            file=sys.stderr,
        )
        return 1
    except ValidationError:
        print(
            "Configuración inválida. Revisa las variables requeridas del entorno o .env.",
            file=sys.stderr,
        )
        return 1
    except SQLAlchemyError:
        print(
            "No se pudo completar la carga. Revisa la conexión SQL Server, los permisos "
            "del usuario y que las migraciones de reservas estén aplicadas.",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(
            "No se pudo completar la carga. Comprueba las dependencias y la configuración del proyecto.",
            file=sys.stderr,
        )
        return 1

    print(f"Carga completada: creadas={creadas}, existentes={existentes}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
