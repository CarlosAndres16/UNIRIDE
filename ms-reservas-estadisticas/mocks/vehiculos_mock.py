"""Mock local del unico endpoint de Vehiculos que consume Reservas."""

from typing import Annotated

from fastapi import Depends, FastAPI, Path

from app.exceptions.exceptions import RecursoNoEncontradoError
from app.schemas.error_schema import CodigoError
from app.security.jwt_service import ConductorAutenticado, getConductorAutenticado, verificarPropietario
from mocks.common import crearMockBase, ejecutarMock
from mocks.data import crearVehiculosEjemplo
from mocks.schemas import VehiculoMock


def crearVehiculosMock(*, vehiculos: list[VehiculoMock] | None = None) -> FastAPI:
    application = crearMockBase("UniRide - Mock Vehiculos")
    ejemplos = crearVehiculosEjemplo() if vehiculos is None else vehiculos
    application.state.vehiculos = {vehiculo.vehiculoId: vehiculo.model_copy(deep=True) for vehiculo in ejemplos}

    @application.get("/api/v1/vehiculos/{vehiculoId}", response_model=VehiculoMock)
    async def consultarVehiculo(
        vehiculoId: Annotated[int, Path(gt=0)],
        conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
    ) -> VehiculoMock:
        vehiculo = application.state.vehiculos.get(vehiculoId)
        if vehiculo is None:
            raise RecursoNoEncontradoError(CodigoError.VEHICULO_NO_ENCONTRADO, "El vehiculo no existe.")
        verificarPropietario(vehiculo.conductorId, conductor)
        return vehiculo

    return application


app = crearVehiculosMock()


if __name__ == "__main__":
    ejecutarMock("mocks.vehiculos_mock:app", "vehiculos")
