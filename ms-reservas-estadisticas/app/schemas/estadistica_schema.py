"""Respuestas de estadisticas con los campos del contrato unificado."""

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _RespuestaEstadistica(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, hide_input_in_errors=True,
    )


class PeriodoSchema(_RespuestaEstadistica):
    desde: date | None
    hasta: date | None

    @model_validator(mode="after")
    def validarOrden(self) -> Self:
        if self.desde is not None and self.hasta is not None and self.desde > self.hasta:
            raise ValueError("El inicio del periodo no puede ser posterior al final.")
        return self


class EstadisticaViajeSchema(_RespuestaEstadistica):
    viajeId: int = Field(strict=True, gt=0)
    vehiculoId: int = Field(strict=True, gt=0)
    cuposOfrecidos: int = Field(strict=True, ge=0)
    totalReservas: int = Field(strict=True, ge=0)
    reservasConfirmadas: int = Field(strict=True, ge=0)
    reservasCanceladas: int = Field(strict=True, ge=0)
    reservasPendientes: int = Field(strict=True, ge=0)
    pasajerosConfirmados: int = Field(strict=True, ge=0)
    cuposDisponibles: int = Field(strict=True, ge=0)
    porcentajeOcupacion: float = Field(ge=0, le=100, allow_inf_nan=False)


class EstadisticaConductorSchema(_RespuestaEstadistica):
    conductorId: int = Field(strict=True, gt=0)
    periodo: PeriodoSchema | None
    viajesConsultados: int = Field(strict=True, ge=0)
    vehiculosUtilizados: int = Field(strict=True, ge=0)
    totalReservas: int = Field(strict=True, ge=0)
    reservasConfirmadas: int = Field(strict=True, ge=0)
    reservasCanceladas: int = Field(strict=True, ge=0)
    pasajerosConfirmados: int = Field(strict=True, ge=0)
    porcentajeOcupacionPromedio: float = Field(ge=0, le=100, allow_inf_nan=False)


class EstadisticaVehiculoSchema(_RespuestaEstadistica):
    vehiculoId: int = Field(strict=True, gt=0)
    conductorId: int = Field(strict=True, gt=0)
    periodo: PeriodoSchema | None
    viajesConsultados: int = Field(strict=True, ge=0)
    totalReservas: int = Field(strict=True, ge=0)
    reservasConfirmadas: int = Field(strict=True, ge=0)
    reservasCanceladas: int = Field(strict=True, ge=0)
    pasajerosConfirmados: int = Field(strict=True, ge=0)
    cuposOfrecidosAcumulados: int = Field(strict=True, ge=0)
    porcentajeOcupacionPromedio: float = Field(ge=0, le=100, allow_inf_nan=False)
