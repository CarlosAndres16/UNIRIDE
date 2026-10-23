"""Modelo de reservas almacenadas en la base de datos del microservicio."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Identity, Index, Integer, PrimaryKeyConstraint, text
from sqlalchemy.dialects.mssql import DATETIME2, NVARCHAR
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.models.base import Base


class EstadoReserva(StrEnum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"


class UtcDateTime(TypeDecorator[datetime]):
    """Guarda UTC sin zona en DATETIME2 y devuelve fechas conscientes de UTC."""

    impl = DATETIME2(precision=6)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fechaReserva debe incluir una zona horaria.")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Reserva(Base):
    """Mapea atributos camelCase a las seis columnas SQL del contrato."""

    __tablename__ = "reservas"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_reservas"),
        CheckConstraint(
            "viaje_id > 0",
            name="ck_reservas_viaje_id_positivo",
        ),
        CheckConstraint(
            "LEN(LTRIM(RTRIM(pasajero_nombre))) > 0",
            name="ck_reservas_pasajero_nombre_no_vacio",
        ),
        CheckConstraint(
            "cupos_reservados >= 1",
            name="ck_reservas_cupos_reservados_minimo",
        ),
        CheckConstraint(
            "estado IN (N'PENDIENTE', N'CONFIRMADA', N'CANCELADA') "
            "AND DATALENGTH(estado) = DATALENGTH(RTRIM(estado))",
            name="ck_reservas_estado_valido",
        ),
        Index("ix_reservas_viaje_estado", "viaje_id", "estado"),
        {"schema": "dbo"},
    )

    id: Mapped[int] = mapped_column(
        "id", Integer, Identity(start=1, increment=1), primary_key=True
    )
    viajeId: Mapped[int] = mapped_column("viaje_id", Integer, nullable=False)
    pasajeroNombre: Mapped[str] = mapped_column(
        "pasajero_nombre", NVARCHAR(150), nullable=False
    )
    cuposReservados: Mapped[int] = mapped_column(
        "cupos_reservados", Integer, nullable=False
    )
    estado: Mapped[str] = mapped_column(
        "estado", NVARCHAR(20, collation="Latin1_General_100_BIN2"), nullable=False
    )
    fechaReserva: Mapped[datetime] = mapped_column(
        "fecha_reserva",
        UtcDateTime(),
        nullable=False,
        # Coincide con la expresion en minusculas que refleja SQL Server.
        server_default=text("sysutcdatetime()"),
    )
