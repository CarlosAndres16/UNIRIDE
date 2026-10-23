"""Contrato de errores públicos del microservicio."""

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class CodigoError(StrEnum):
    SOLICITUD_INVALIDA = "SOLICITUD_INVALIDA"
    CAMPO_OBLIGATORIO_FALTANTE = "CAMPO_OBLIGATORIO_FALTANTE"
    FORMATO_INVALIDO = "FORMATO_INVALIDO"
    FECHA_HORA_INVALIDA = "FECHA_HORA_INVALIDA"
    CAPACIDAD_INVALIDA = "CAPACIDAD_INVALIDA"
    NO_AUTENTICADO = "NO_AUTENTICADO"
    NO_AUTORIZADO = "NO_AUTORIZADO"
    VIAJE_NO_ENCONTRADO = "VIAJE_NO_ENCONTRADO"
    RESERVA_NO_ENCONTRADA = "RESERVA_NO_ENCONTRADA"
    VEHICULO_NO_ENCONTRADO = "VEHICULO_NO_ENCONTRADO"
    OPERACION_NO_PERMITIDA_POR_ESTADO = "OPERACION_NO_PERMITIDA_POR_ESTADO"
    ERROR_INTERNO = "ERROR_INTERNO"
    SERVICIO_DEPENDIENTE_NO_DISPONIBLE = "SERVICIO_DEPENDIENTE_NO_DISPONIBLE"


ESTADO_POR_CODIGO: Mapping[CodigoError, int] = MappingProxyType(
    {
        CodigoError.SOLICITUD_INVALIDA: 400,
        CodigoError.CAMPO_OBLIGATORIO_FALTANTE: 400,
        CodigoError.FORMATO_INVALIDO: 400,
        CodigoError.FECHA_HORA_INVALIDA: 400,
        CodigoError.CAPACIDAD_INVALIDA: 400,
        CodigoError.NO_AUTENTICADO: 401,
        CodigoError.NO_AUTORIZADO: 403,
        CodigoError.VIAJE_NO_ENCONTRADO: 404,
        CodigoError.RESERVA_NO_ENCONTRADA: 404,
        CodigoError.VEHICULO_NO_ENCONTRADO: 404,
        CodigoError.OPERACION_NO_PERMITIDA_POR_ESTADO: 409,
        CodigoError.ERROR_INTERNO: 500,
        CodigoError.SERVICIO_DEPENDIENTE_NO_DISPONIBLE: 503,
    }
)


class DetalleError(BaseModel):
    """Describe únicamente el campo inválido y un problema público controlado."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
        str_strip_whitespace=True,
    )

    campo: str = Field(min_length=1)
    problema: str = Field(min_length=1)


class ErrorResponse(BaseModel):
    """Respuesta JSON con UTC, identificador UUID y códigos del contrato."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    status: int = Field(strict=True)
    error: CodigoError
    message: str = Field(strict=True, min_length=1)
    path: str = Field(strict=True, min_length=1)
    correlationId: UUID
    detalles: list[DetalleError] | None = None

    @field_validator("timestamp")
    @classmethod
    def normalizarTimestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_serializer("timestamp", when_used="json")
    def serializarTimestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    @model_validator(mode="after")
    def validarContratoError(self) -> Self:
        if ESTADO_POR_CODIGO[self.error] != self.status:
            raise ValueError("El código de error no corresponde al estado HTTP.")
        if self.status == 400 and self.detalles is None:
            self.detalles = []
        elif self.detalles is not None and self.status != 400:
            raise ValueError("Los detalles de validación solo se permiten en errores 400.")
        return self
