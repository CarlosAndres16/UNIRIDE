"""Contratos de registro e inicio de sesión, con contraseñas protegidas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints, field_validator


Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150, strict=True)]
Telefono = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30, strict=True)]


class RegistrarConductorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    nombre: Nombre
    correo: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=8, repr=False)
    telefono: Telefono | None = None

    @field_validator("correo", mode="before")
    @classmethod
    def normalizarCorreo(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    correo: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, repr=False)

    @field_validator("correo", mode="before")
    @classmethod
    def normalizarCorreo(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accessToken: str
    tokenType: Literal["Bearer"] = "Bearer"
    expiresIn: int = Field(gt=0)
    conductorId: int = Field(ge=1, le=2_147_483_647)
