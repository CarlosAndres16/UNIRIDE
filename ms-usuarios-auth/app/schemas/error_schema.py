"""Formato contractual común a todos los errores HTTP."""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: AwareDatetime
    status: int = Field(ge=400, le=599)
    error: str
    message: str
    path: str
    correlationId: str
    detalles: list[dict[str, str]] | None = None

    @field_validator("timestamp")
    @classmethod
    def normalizarTimestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
