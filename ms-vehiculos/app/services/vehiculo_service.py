"""Reglas del contrato: cada recurso es del conductor del token (D-14)."""

from app.exceptions.exceptions import AppException
from app.repositories.vehiculo_repository import VehiculoRepository
from app.schemas.vehiculo_schema import (
    ActualizarVehiculoRequest,
    CrearVehiculoRequest,
    ListaVehiculosResponse,
    VehiculoResponse,
)


class VehiculoService:
    def __init__(self, repository: VehiculoRepository) -> None:
        self._repository = repository

    def registrar(self, conductorId: int, solicitud: CrearVehiculoRequest) -> VehiculoResponse:
        if solicitud.conductorId is not None and solicitud.conductorId != conductorId:
            raise AppException(
                403, "NO_AUTORIZADO",
                "No puede registrar vehículos a nombre de otro conductor.",
            )
        fila = self._repository.crear(
            conductorId, solicitud.model_dump(exclude={"conductorId"})
        )
        return VehiculoResponse.desdeFila(fila)

    def listar(self, conductorId: int) -> ListaVehiculosResponse:
        filas = self._repository.listarPorConductor(conductorId)
        return ListaVehiculosResponse(datos=[VehiculoResponse.desdeFila(f) for f in filas])

    def consultar(self, conductorId: int, vehiculoId: int) -> VehiculoResponse:
        return VehiculoResponse.desdeFila(self._obtenerPropio(conductorId, vehiculoId))

    def actualizar(
        self, conductorId: int, vehiculoId: int, solicitud: ActualizarVehiculoRequest
    ) -> VehiculoResponse:
        self._obtenerPropio(conductorId, vehiculoId)
        fila = self._repository.actualizar(vehiculoId, solicitud.model_dump())
        if fila is None:
            raise self._noEncontrado(vehiculoId)
        return VehiculoResponse.desdeFila(fila)

    def darDeBaja(self, conductorId: int, vehiculoId: int) -> None:
        self._obtenerPropio(conductorId, vehiculoId)
        self._repository.darDeBaja(vehiculoId)

    def _obtenerPropio(self, conductorId: int, vehiculoId: int) -> dict:
        fila = self._repository.obtener(vehiculoId)
        if fila is None:
            raise self._noEncontrado(vehiculoId)
        if fila["conductor_id"] != conductorId:
            raise AppException(403, "NO_AUTORIZADO", "El vehículo pertenece a otro conductor.")
        return fila

    @staticmethod
    def _noEncontrado(vehiculoId: int) -> AppException:
        return AppException(
            404, "VEHICULO_NO_ENCONTRADO", f"No existe un vehículo con id {vehiculoId}."
        )
