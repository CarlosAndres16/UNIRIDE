"""Alias del contrato compartido; los mocks conservan sus nombres de fase 7."""

from app.schemas.integracion_schema import (
    EstadoFiltroViaje,
    EstadoVehiculo,
    EstadoViaje,
    ListaViajesExterna as ListaViajes,
    ModeloExterno as ModeloMock,
    OcupacionEntrada,
    OcupacionExterna as OcupacionRespuesta,
    Paginacion,
    PuntoExterno as PuntoMock,
    VehiculoExterno as VehiculoMock,
    ViajeExterno as ViajeMock,
)

__all__ = [
    "EstadoFiltroViaje", "EstadoVehiculo", "EstadoViaje", "ListaViajes",
    "ModeloMock", "OcupacionEntrada", "OcupacionRespuesta", "Paginacion",
    "PuntoMock", "VehiculoMock", "ViajeMock",
]
