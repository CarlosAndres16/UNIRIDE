"""La tabla de conductores pertenece exclusivamente a este servicio."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Identity, Integer, Unicode, UniqueConstraint, text
from sqlalchemy.dialects.mssql import BIT, DATETIME2, NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.config.database import Base


def utcNowSinZona() -> datetime:
    """SQL Server DATETIME2 guarda UTC sin información de zona horaria."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conductor(Base):
    __tablename__ = "conductores"
    __table_args__ = (
        UniqueConstraint("correo", name="uq_conductores_correo"),
        {"schema": "dbo"},
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    nombre: Mapped[str] = mapped_column(
        Unicode(150).with_variant(NVARCHAR(150), "mssql"), nullable=False
    )
    correo: Mapped[str] = mapped_column(
        Unicode(254).with_variant(NVARCHAR(254), "mssql"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        Unicode(255).with_variant(NVARCHAR(255), "mssql"), nullable=False
    )
    telefono: Mapped[str | None] = mapped_column(
        Unicode(30).with_variant(NVARCHAR(30), "mssql"), nullable=True
    )
    activo: Mapped[bool] = mapped_column(
        Boolean().with_variant(BIT(), "mssql"),
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME2(precision=6), "mssql"),
        nullable=False,
        default=utcNowSinZona,
        server_default=text("SYSUTCDATETIME()"),
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME2(precision=6), "mssql"),
        nullable=False,
        server_default=text("SYSUTCDATETIME()"),
        default=utcNowSinZona,
        onupdate=utcNowSinZona,
    )
