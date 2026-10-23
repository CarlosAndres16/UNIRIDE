"""Fixtures deterministas; cada fabrica devuelve objetos nuevos en memoria."""

from datetime import UTC, date, datetime, timedelta

from mocks.schemas import EstadoVehiculo, EstadoViaje, PuntoMock, VehiculoMock, ViajeMock


def crearViajesEjemplo() -> list[ViajeMock]:
    origen = PuntoMock(descripcion="UNIMINUTO Calle 80", latitud=4.0, longitud=-74.0)
    destino = PuntoMock(descripcion="Chía", latitud=4.0, longitud=-74.0)
    fechaBase = datetime(2026, 10, 1, 14, tzinfo=UTC)

    def crear(viajeId, conductorId, vehiculoId, fechaSalida, estado, capacidad=4, disponibles=4, hora="07:00"):
        return ViajeMock(
            viajeId=viajeId, conductorId=conductorId, vehiculoId=vehiculoId,
            origen=origen, destino=destino, fechaSalida=fechaSalida,
            horaSalida=hora, capacidad=capacidad, cuposDisponibles=disponibles,
            estado=estado, version=1, fechaCreacion=fechaBase, fechaActualizacion=fechaBase,
        )

    viajes = [
        crear(305, 25, 12, date(2026, 10, 25), EstadoViaje.ACTIVO, disponibles=2),
        crear(306, 25, 12, date(2026, 10, 1), EstadoViaje.FINALIZADO),
        crear(307, 25, 12, date(2026, 10, 31), EstadoViaje.CANCELADO),
        crear(308, 25, 13, date(2026, 10, 26), EstadoViaje.ACTIVO, capacidad=2, disponibles=2),
        crear(309, 26, 14, date(2026, 10, 27), EstadoViaje.ACTIVO),
    ]
    # Conductor separado para demostrar 51 resultados sin alterar el ejemplo 305.
    for indice in range(51):
        hora = (datetime(2026, 10, 25) + timedelta(minutes=20 * indice)).strftime("%H:%M")
        viajes.append(crear(1000 + indice, 27, 16, date(2026, 10, 25), EstadoViaje.ACTIVO, hora=hora))
    return viajes


def crearVehiculosEjemplo() -> list[VehiculoMock]:
    return [
        VehiculoMock(vehiculoId=12, conductorId=25, placa="ABC123", marca="Renault", modelo="Logan", color="Gris", tipo="CARRO", capacidad=4, estado=EstadoVehiculo.ACTIVO),
        VehiculoMock(vehiculoId=13, conductorId=25, placa="DEF456", marca="Chevrolet", modelo="Spark", color="Azul", tipo="CARRO", capacidad=2, estado=EstadoVehiculo.ACTIVO),
        VehiculoMock(vehiculoId=14, conductorId=26, placa="GHI789", marca="Kia", modelo="Rio", color="Blanco", tipo="CARRO", capacidad=4, estado=EstadoVehiculo.ACTIVO),
        VehiculoMock(vehiculoId=15, conductorId=25, placa="JKL012", marca="Renault", modelo="Sandero", color="Rojo", tipo="CARRO", capacidad=4, estado=EstadoVehiculo.INACTIVO),
        VehiculoMock(vehiculoId=16, conductorId=27, placa="MNO345", marca="Mazda", modelo="2", color="Negro", tipo="CARRO", capacidad=4, estado=EstadoVehiculo.ACTIVO),
    ]
