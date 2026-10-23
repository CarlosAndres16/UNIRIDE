"""DTO de consulta y reemplazo de los datos editables del conductor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth_schema import Nombre, Telefono

if TYPE_CHECKING:
    from app.models.conductor import Conductor


class ActualizarConductorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    nombre: Nombre
    telefono: Telefono | None = None


class ConductorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conductorId: int = Field(ge=1, le=2_147_483_647)
    nombre: str
    correo: EmailStr
    telefono: str | None
    activo: bool

    @classmethod
    def fromConductor(cls, conductor: Conductor) -> ConductorResponse:
        """Mapea explícitamente SQL snake_case sin exponer hashes ni fechas internas."""
        return cls(
            conductorId=conductor.id,
            nombre=conductor.nombre,
            correo=conductor.correo,
            telefono=conductor.telefono,
            activo=conductor.activo,
        )
