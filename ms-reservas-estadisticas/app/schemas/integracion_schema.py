"""DTO compartidos del contrato para proveedores HTTP y sus mocks locales."""

from datetime import UTC, date, datetime
from enum import StrEnum
import re
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator


def validarTimestampExterno(value):
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})",
        value,
    ):
        raise ValueError("El timestamp debe usar ISO 8601 con zona horaria explicita.")
    return value


class EstadoViaje(StrEnum):
    ACTIVO = "ACTIVO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"


class EstadoFiltroViaje(StrEnum):
    ACTIVO = "ACTIVO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"
    TODOS = "TODOS"


class EstadoVehiculo(StrEnum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


class ModeloExterno(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class PuntoExterno(ModeloExterno):
    descripcion: str = Field(strict=True, min_length=1)
    latitud: float = Field(strict=True, ge=-90, le=90)
    longitud: float = Field(strict=True, ge=-180, le=180)


class ViajeExterno(ModeloExterno):
    viajeId: int = Field(strict=True, gt=0)
    conductorId: int = Field(strict=True, gt=0)
    vehiculoId: int = Field(strict=True, gt=0)
    origen: PuntoExterno
    destino: PuntoExterno
    fechaSalida: date
    horaSalida: str = Field(strict=True, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    capacidad: int = Field(strict=True, ge=1, le=8)
    cuposDisponibles: int = Field(strict=True, ge=0)
    estado: EstadoViaje
    version: int = Field(strict=True, ge=1)
    fechaCreacion: AwareDatetime
    fechaActualizacion: AwareDatetime

    @field_validator("fechaSalida", mode="before")
    @classmethod
    def validarFecha(cls, value):
        if type(value) is date:
            return value
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("La fecha debe usar YYYY-MM-DD.")
        return value

    @field_validator("fechaCreacion", "fechaActualizacion", mode="before")
    @classmethod
    def validarTipoTimestamp(cls, value):
        return validarTimestampExterno(value)

    @model_validator(mode="after")
    def validarCupos(self) -> Self:
        if self.cuposDisponibles > self.capacidad:
            raise ValueError("Los cupos disponibles no pueden superar la capacidad.")
        return self

    @field_serializer("fechaCreacion", "fechaActualizacion", when_used="json")
    def serializarUtc(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class VehiculoExterno(ModeloExterno):
    vehiculoId: int = Field(strict=True, gt=0)
    conductorId: int = Field(strict=True, gt=0)
    placa: str = Field(strict=True, min_length=1)
    marca: str = Field(strict=True, min_length=1)
    modelo: str = Field(strict=True, min_length=1)
    color: str = Field(strict=True, min_length=1)
    tipo: str = Field(strict=True, min_length=1)
    capacidad: int = Field(strict=True, ge=1)
    estado: EstadoVehiculo


class Paginacion(ModeloExterno):
    pagina: int = Field(strict=True, ge=1)
    tamano: int = Field(strict=True, ge=1, le=50)
    totalElementos: int = Field(strict=True, ge=0)
    totalPaginas: int = Field(strict=True, ge=0)


class ListaViajesExterna(ModeloExterno):
    datos: list[ViajeExterno]
    paginacion: Paginacion


class OcupacionEntrada(ModeloExterno):
    cuposOcupados: int = Field(strict=True, ge=0)


class OcupacionExterna(ModeloExterno):
    viajeId: int = Field(strict=True, gt=0)
    capacidad: int = Field(strict=True, ge=1, le=8)
    cuposDisponibles: int = Field(strict=True, ge=0)
    estado: EstadoViaje
    version: int = Field(strict=True, ge=1)
    fechaActualizacion: AwareDatetime

    @field_validator("fechaActualizacion", mode="before")
    @classmethod
    def validarTipoTimestamp(cls, value):
        return validarTimestampExterno(value)

    @model_validator(mode="after")
    def validarCupos(self) -> Self:
        if self.cuposDisponibles > self.capacidad:
            raise ValueError("Los cupos disponibles no pueden superar la capacidad.")
        return self

    @field_serializer("fechaActualizacion", when_used="json")
    def serializarUtc(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
