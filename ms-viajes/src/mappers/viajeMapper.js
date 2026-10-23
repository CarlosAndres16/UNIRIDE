const { aIsoUtc } = require('../utils/fechas');

// Fila de BD (snake_case) -> objeto Viaje del contrato (camelCase)
function aViajeResponse(fila) {
  return {
    viajeId: fila.id,
    conductorId: fila.conductor_id,
    vehiculoId: fila.vehiculo_id,
    origen: {
      descripcion: fila.origen_descripcion,
      latitud: fila.origen_latitud,
      longitud: fila.origen_longitud,
    },
    destino: {
      descripcion: fila.destino_descripcion,
      latitud: fila.destino_latitud,
      longitud: fila.destino_longitud,
    },
    fechaSalida: fila.fecha_salida,
    horaSalida: String(fila.hora_salida).slice(0, 5),
    capacidad: fila.capacidad,
    cuposDisponibles: fila.capacidad - fila.cupos_ocupados,
    estado: fila.estado,
    version: fila.version,
    fechaCreacion: aIsoUtc(fila.fecha_creacion),
    fechaActualizacion: aIsoUtc(fila.fecha_actualizacion),
  };
}

// Respuesta de PUT /viajes/{viajeId}/ocupacion
function aOcupacionResponse(fila) {
  return {
    viajeId: fila.id,
    capacidad: fila.capacidad,
    cuposDisponibles: fila.capacidad - fila.cupos_ocupados,
    estado: fila.estado,
    version: fila.version,
    fechaActualizacion: aIsoUtc(fila.fecha_actualizacion),
  };
}

module.exports = { aViajeResponse, aOcupacionResponse };