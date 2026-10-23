"""Consulta y actualización autorizadas por identidad del propietario."""

from app.exceptions.exceptions import AppException
from app.models.conductor import Conductor
from app.repositories.conductor_repository import ConductorRepository
from app.schemas.conductor_schema import ActualizarConductorRequest, ConductorResponse


class ConductorService:
    def __init__(self, repository: ConductorRepository) -> None:
        self.repository = repository

    def _buscarPropio(self, conductorId: int, conductorIdAutenticado: int) -> Conductor:
        if conductorId != conductorIdAutenticado:
            raise AppException(
                status=403,
                error="NO_AUTORIZADO",
                message="Solo puedes acceder a tu propio recurso de conductor.",
            )
        conductor = self.repository.buscarPorId(conductorId)
        if conductor is None:
            raise AppException(
                status=404,
                error="CONDUCTOR_NO_ENCONTRADO",
                message=f"No existe un conductor con id {conductorId}.",
            )
        return conductor

    def consultar(self, conductorId: int, conductorIdAutenticado: int) -> ConductorResponse:
        return ConductorResponse.fromConductor(self._buscarPropio(conductorId, conductorIdAutenticado))

    def actualizar(
        self,
        conductorId: int,
        conductorIdAutenticado: int,
        request: ActualizarConductorRequest,
    ) -> ConductorResponse:
        conductor = self._buscarPropio(conductorId, conductorIdAutenticado)
        conductorActualizado = self.repository.actualizar(
            conductor,
            nombre=request.nombre,
            telefono=request.telefono,
        )
        return ConductorResponse.fromConductor(conductorActualizado)
