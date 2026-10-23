"""Respuestas de reservas con los seis campos del contrato."""

from datetime import UTC, datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.models.reserva import EstadoReserva


class ReservaSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="forbid",
        frozen=True, hide_input_in_errors=True,
    )

    reservaId: int = Field(validation_alias="id", strict=True, gt=0)
    viajeId: int = Field(strict=True, gt=0)
    pasajeroNombre: str = Field(strict=True, min_length=1, max_length=150)
    cuposReservados: int = Field(strict=True, ge=1)
    estado: EstadoReserva
    fechaReserva: AwareDatetime = Field(json_schema_extra={"format": "date-time"})

    @field_serializer("fechaReserva", when_used="json")
    def serializarUtc(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ReservasViajeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    viajeId: int = Field(strict=True, gt=0)
    total: int = Field(strict=True, ge=0)
    datos: list[ReservaSchema]

    @model_validator(mode="after")
    def validarLista(self) -> Self:
        if self.total != len(self.datos):
            raise ValueError("El total no corresponde a los datos.")
        if any(reserva.viajeId != self.viajeId for reserva in self.datos):
            raise ValueError("Las reservas deben corresponder al viaje consultado.")
        if len({reserva.reservaId for reserva in self.datos}) != len(self.datos):
            raise ValueError("La lista no debe contener reservas duplicadas.")
        return self
