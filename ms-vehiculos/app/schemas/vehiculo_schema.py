"""DTO del contrato: JSON en camelCase, ids enteros, estado en mayúsculas."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class _VehiculoBaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    placa: str = Field(min_length=1, max_length=10)
    marca: str = Field(min_length=1, max_length=50)
    modelo: str = Field(min_length=1, max_length=50)
    color: str = Field(min_length=1, max_length=30)
    tipo: str = Field(min_length=1, max_length=30)
    capacidad: StrictInt = Field(ge=1, le=2_147_483_647)

    @field_validator("placa")
    @classmethod
    def placaEnMayusculas(cls, value: str) -> str:
        return value.upper()


class CrearVehiculoRequest(_VehiculoBaseRequest):
    # conductorId sale del token; si se envía, debe coincidir (lo valida el servicio).
    conductorId: StrictInt | None = Field(default=None, gt=0)


class ActualizarVehiculoRequest(_VehiculoBaseRequest):
    pass


class VehiculoResponse(BaseModel):
    vehiculoId: int
    conductorId: int
    placa: str
    marca: str
    modelo: str
    color: str
    tipo: str
    capacidad: int
    estado: str

    @classmethod
    def desdeFila(cls, fila: dict) -> "VehiculoResponse":
        """Conversión snake_case (tabla) a camelCase (JSON)."""
        return cls(
            vehiculoId=fila["id"],
            conductorId=fila["conductor_id"],
            placa=fila["placa"],
            marca=fila["marca"],
            modelo=fila["modelo"],
            color=fila["color"],
            tipo=fila["tipo"],
            capacidad=fila["capacidad"],
            estado=fila["estado"],
        )


class ListaVehiculosResponse(BaseModel):
    datos: list[VehiculoResponse]
