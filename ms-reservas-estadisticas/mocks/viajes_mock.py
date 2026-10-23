"""Mock parcial de Viajes: subconjunto utilizado por Reservas y Estadisticas."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Path, Query, Request

from app.exceptions.exceptions import (
    ExcepcionAplicacion,
    RecursoNoEncontradoError,
    SolicitudInvalidaError,
)
from app.schemas.error_schema import CodigoError
from app.security.jwt_service import (
    ConductorAutenticado,
    getConductorAutenticado,
    verificarPropietario,
)
from mocks.common import crearMockBase, ejecutarMock, validarPeriodo, verificarServiceKey
from mocks.data import crearViajesEjemplo
from mocks.schemas import (
    EstadoFiltroViaje,
    EstadoViaje,
    ListaViajes,
    OcupacionEntrada,
    OcupacionRespuesta,
    Paginacion,
    ViajeMock,
)


def _obtenerViaje(request: Request, viajeId: int) -> ViajeMock:
    viaje = request.app.state.viajes.get(viajeId)
    if viaje is None:
        raise RecursoNoEncontradoError(
            CodigoError.VIAJE_NO_ENCONTRADO,
            f"No existe un viaje con id {viajeId}.",
        )
    return viaje


def _respuestaOcupacion(viaje: ViajeMock) -> OcupacionRespuesta:
    return OcupacionRespuesta(
        viajeId=viaje.viajeId,
        capacidad=viaje.capacidad,
        cuposDisponibles=viaje.cuposDisponibles,
        estado=viaje.estado,
        version=viaje.version,
        fechaActualizacion=viaje.fechaActualizacion,
    )


def crearViajesMock(*, viajes: list[ViajeMock] | None = None) -> FastAPI:
    """Crea una aplicacion con datos en memoria independientes por instancia."""

    app = crearMockBase("Viajes")
    datosIniciales = crearViajesEjemplo() if viajes is None else viajes
    app.state.viajes = {
        viaje.viajeId: viaje.model_copy(deep=True) for viaje in datosIniciales
    }

    @app.get("/api/v1/viajes", response_model=ListaViajes)
    async def listarViajes(
        request: Request,
        conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
        conductorId: Annotated[int | None, Query(gt=0)] = None,
        vehiculoId: Annotated[int | None, Query(gt=0)] = None,
        desde: Annotated[str | None, Query()] = None,
        hasta: Annotated[str | None, Query()] = None,
        estado: Annotated[EstadoFiltroViaje, Query()] = EstadoFiltroViaje.ACTIVO,
        pagina: Annotated[int, Query(ge=1)] = 1,
        tamano: Annotated[int, Query(ge=1, le=50)] = 20,
    ) -> ListaViajes:
        # La busqueda del contrato es abierta a conductores autenticados; no
        # aplica un filtro implicito por el sub del JWT.
        fechaDesde, fechaHasta = validarPeriodo(desde, hasta)
        seleccionados = [
            viaje
            for viaje in sorted(
                request.app.state.viajes.values(), key=lambda item: item.viajeId
            )
            if (conductorId is None or viaje.conductorId == conductorId)
            and (vehiculoId is None or viaje.vehiculoId == vehiculoId)
            and (fechaDesde is None or viaje.fechaSalida >= fechaDesde)
            and (fechaHasta is None or viaje.fechaSalida <= fechaHasta)
            and (estado == EstadoFiltroViaje.TODOS or viaje.estado.value == estado.value)
        ]
        totalElementos = len(seleccionados)
        inicio = (pagina - 1) * tamano
        return ListaViajes(
            datos=seleccionados[inicio : inicio + tamano],
            paginacion=Paginacion(
                pagina=pagina,
                tamano=tamano,
                totalElementos=totalElementos,
                totalPaginas=(totalElementos + tamano - 1) // tamano,
            ),
        )

    @app.get("/api/v1/viajes/{viajeId}", response_model=ViajeMock)
    async def obtenerViaje(
        request: Request,
        viajeId: Annotated[int, Path(gt=0)],
        conductor: Annotated[ConductorAutenticado, Depends(getConductorAutenticado)],
    ) -> ViajeMock:
        viaje = _obtenerViaje(request, viajeId)
        verificarPropietario(viaje.conductorId, conductor)
        return viaje

    @app.put(
        "/api/v1/viajes/{viajeId}/ocupacion",
        response_model=OcupacionRespuesta,
        dependencies=[Depends(verificarServiceKey)],
    )
    async def actualizarOcupacion(
        request: Request,
        viajeId: Annotated[int, Path(gt=0)],
        ocupacion: OcupacionEntrada,
    ) -> OcupacionRespuesta:
        viaje = _obtenerViaje(request, viajeId)
        if viaje.estado != EstadoViaje.ACTIVO:
            raise ExcepcionAplicacion(
                409,
                CodigoError.OPERACION_NO_PERMITIDA_POR_ESTADO,
                "Solo se puede actualizar la ocupacion de un viaje ACTIVO.",
            )
        if ocupacion.cuposOcupados > viaje.capacidad:
            raise SolicitudInvalidaError(
                "Los cupos ocupados no pueden superar la capacidad del viaje.",
                detalles=[
                    {
                        "campo": "cuposOcupados",
                        "problema": "No puede superar la capacidad del viaje.",
                    }
                ],
                error=CodigoError.CAPACIDAD_INVALIDA,
            )

        cuposDisponibles = viaje.capacidad - ocupacion.cuposOcupados
        if cuposDisponibles == viaje.cuposDisponibles:
            return _respuestaOcupacion(viaje)

        # El cuerpo contiene el total ocupado. Sin await entre lectura y
        # escritura, esta actualizacion en memoria no se intercala en el loop.
        actualizado = viaje.model_copy(
            update={
                "cuposDisponibles": cuposDisponibles,
                "version": viaje.version + 1,
                "fechaActualizacion": datetime.now(UTC),
            }
        )
        request.app.state.viajes[viajeId] = actualizado
        return _respuestaOcupacion(actualizado)

    return app


app = crearViajesMock()


if __name__ == "__main__":
    ejecutarMock("mocks.viajes_mock:app", "viajes")
