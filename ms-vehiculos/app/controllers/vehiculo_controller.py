"""Los 5 endpoints de Vehículos (sección 4)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.dependencies import getConductorId, getVehiculoService
from app.schemas.vehiculo_schema import (
    ActualizarVehiculoRequest,
    CrearVehiculoRequest,
    ListaVehiculosResponse,
    VehiculoResponse,
)
from app.services.vehiculo_service import VehiculoService

router = APIRouter(prefix="/api/v1/vehiculos", tags=["Vehículos"])

ConductorIdDep = Annotated[int, Depends(getConductorId)]
ServicioDep = Annotated[VehiculoService, Depends(getVehiculoService)]
VehiculoIdPath = Annotated[int, Path(gt=0, le=2_147_483_647)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=VehiculoResponse)
def registrarVehiculo(
    solicitud: CrearVehiculoRequest, conductorId: ConductorIdDep, servicio: ServicioDep
):
    return servicio.registrar(conductorId, solicitud)


@router.get("", response_model=ListaVehiculosResponse)
def listarVehiculos(conductorId: ConductorIdDep, servicio: ServicioDep):
    return servicio.listar(conductorId)


@router.get("/{vehiculoId}", response_model=VehiculoResponse)
def consultarVehiculo(
    vehiculoId: VehiculoIdPath, conductorId: ConductorIdDep, servicio: ServicioDep
):
    return servicio.consultar(conductorId, vehiculoId)


@router.put("/{vehiculoId}", response_model=VehiculoResponse)
def modificarVehiculo(
    vehiculoId: VehiculoIdPath,
    solicitud: ActualizarVehiculoRequest,
    conductorId: ConductorIdDep,
    servicio: ServicioDep,
):
    return servicio.actualizar(conductorId, vehiculoId, solicitud)


@router.delete("/{vehiculoId}", status_code=status.HTTP_204_NO_CONTENT)
def darDeBajaVehiculo(
    vehiculoId: VehiculoIdPath, conductorId: ConductorIdDep, servicio: ServicioDep
):
    servicio.darDeBaja(conductorId, vehiculoId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
