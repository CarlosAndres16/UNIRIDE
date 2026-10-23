const repo = require('../repositories/viajeRepository');
const vehiculosClient = require('../clients/vehiculosClient');
const { AppError } = require('../utils/errores');

const noEncontrado = (id) =>
  new AppError(404, 'VIAJE_NO_ENCONTRADO', `No existe un viaje con id ${id}.`);

const estadoNoPermitido = (accion, estado) =>
  new AppError(
    409,
    'OPERACION_NO_PERMITIDA_POR_ESTADO',
    `No se puede ${accion} un viaje en estado ${estado}.`
  );

// ctx = { conductorId, token, correlationId }
async function validarVehiculo(vehiculoId, ctx) {
  const vehiculo = await vehiculosClient.obtenerVehiculo(vehiculoId, ctx);
  if (vehiculo.conductorId !== ctx.conductorId) {
    throw new AppError(403, 'NO_AUTORIZADO', 'El vehículo pertenece a otro conductor.');
  }
  if (vehiculo.estado !== 'ACTIVO') {
    throw new AppError(409, 'VEHICULO_INACTIVO', `El vehículo ${vehiculoId} está inactivo.`);
  }
}

async function obtenerViajePropio(id, conductorId) {
  const viaje = await repo.buscarPorId(id);
  if (!viaje) throw noEncontrado(id);
  if (viaje.conductor_id !== conductorId) {
    throw new AppError(403, 'NO_AUTORIZADO', 'El viaje pertenece a otro conductor.');
  }
  return viaje;
}

function aColumnas(d) {
  const c = {};
  if (d.vehiculoId !== undefined) c.vehiculo_id = d.vehiculoId;
  if (d.origen !== undefined) {
    c.origen_descripcion = d.origen.descripcion;
    c.origen_latitud = d.origen.latitud;
    c.origen_longitud = d.origen.longitud;
  }
  if (d.destino !== undefined) {
    c.destino_descripcion = d.destino.descripcion;
    c.destino_latitud = d.destino.latitud;
    c.destino_longitud = d.destino.longitud;
  }
  if (d.fechaSalida !== undefined) c.fecha_salida = d.fechaSalida;
  if (d.horaSalida !== undefined) c.hora_salida = d.horaSalida;
  if (d.capacidad !== undefined) c.capacidad = d.capacidad;
  return c;
}

async function crear(ctx, datos, idempotencyKey) {
  if (idempotencyKey) {
    const previo = await repo.buscarPorIdempotencia(ctx.conductorId, idempotencyKey);
    if (previo) return previo;
  }

  await validarVehiculo(datos.vehiculoId, ctx);

  const duplicado = await repo.existeDuplicado(
    ctx.conductorId,
    datos.vehiculoId,
    datos.fechaSalida,
    datos.horaSalida
  );
  if (duplicado) {
    throw new AppError(
      409,
      'VIAJE_DUPLICADO',
      'Ya tienes un viaje activo con ese vehículo, fecha y hora.'
    );
  }

  try {
    return await repo.crear({
      ...datos,
      conductorId: ctx.conductorId,
      idempotencyKey: idempotencyKey || null,
    });
  } catch (err) {
    // Dos peticiones simultáneas con la misma Idempotency-Key
    if (err.code === '23505' && idempotencyKey) {
      const previo = await repo.buscarPorIdempotencia(ctx.conductorId, idempotencyKey);
      if (previo) return previo;
    }
    throw err;
  }
}

async function consultar(id) {
  const viaje = await repo.buscarPorId(id);
  if (!viaje) throw noEncontrado(id);
  return viaje;
}

async function buscar(filtros) {
  const { filas, total } = await repo.buscar(filtros);
  return {
    filas,
    paginacion: {
      pagina: filtros.pagina,
      tamano: filtros.tamano,
      totalElementos: total,
      totalPaginas: Math.ceil(total / filtros.tamano),
    },
  };
}

async function modificar(ctx, id, datos, versionEsperada) {
  const viaje = await obtenerViajePropio(id, ctx.conductorId);

  if (versionEsperada !== undefined && versionEsperada !== viaje.version) {
    throw new AppError(
      409,
      'CONFLICTO_DE_VERSION',
      `La versión actual del viaje es ${viaje.version}. Consulta el viaje de nuevo.`
    );
  }
  if (viaje.estado !== 'ACTIVO') throw estadoNoPermitido('modificar', viaje.estado);

  if (datos.vehiculoId !== undefined && datos.vehiculoId !== viaje.vehiculo_id) {
    await validarVehiculo(datos.vehiculoId, ctx);
  }

  if (datos.capacidad !== undefined && datos.capacidad < viaje.cupos_ocupados) {
    throw new AppError(
      409,
      'VIAJE_CON_RESERVAS',
      `La capacidad no puede ser menor que los cupos ya ocupados (${viaje.cupos_ocupados}).`
    );
  }

  const actualizado = await repo.actualizar(id, viaje.version, aColumnas(datos));
  if (!actualizado) {
    throw new AppError(
      409,
      'CONFLICTO_DE_VERSION',
      'El viaje cambió mientras se procesaba la solicitud. Consúltalo de nuevo.'
    );
  }
  return actualizado;
}

async function cancelar(ctx, id) {
  const viaje = await obtenerViajePropio(id, ctx.conductorId);
  if (viaje.estado === 'CANCELADO') {
    throw new AppError(409, 'VIAJE_YA_CANCELADO', `El viaje ${id} ya está cancelado.`);
  }
  if (viaje.estado !== 'ACTIVO') throw estadoNoPermitido('cancelar', viaje.estado);

  const actualizado = await repo.cambiarEstado(id, 'CANCELADO');
  if (!actualizado) throw estadoNoPermitido('cancelar', 'no ACTIVO');
  return actualizado;
}

async function finalizar(ctx, id) {
  const viaje = await obtenerViajePropio(id, ctx.conductorId);
  if (viaje.estado !== 'ACTIVO') throw estadoNoPermitido('finalizar', viaje.estado);

  const actualizado = await repo.cambiarEstado(id, 'FINALIZADO');
  if (!actualizado) throw estadoNoPermitido('finalizar', 'no ACTIVO');
  return actualizado;
}

async function actualizarOcupacion(id, cuposOcupados) {
  const viaje = await repo.buscarPorId(id);
  if (!viaje) throw noEncontrado(id);

  if (cuposOcupados > viaje.capacidad) {
    throw new AppError(
      400,
      'CAPACIDAD_INVALIDA',
      `cuposOcupados no puede ser mayor que la capacidad (${viaje.capacidad}).`,
      [{ campo: 'cuposOcupados', problema: `No puede ser mayor que ${viaje.capacidad}` }]
    );
  }
  if (viaje.estado !== 'ACTIVO') throw estadoNoPermitido('actualizar la ocupación de', viaje.estado);

  const actualizado = await repo.actualizarOcupacion(id, cuposOcupados);
  if (!actualizado) throw estadoNoPermitido('actualizar la ocupación de', 'no ACTIVO');
  return actualizado;
}

module.exports = {
  crear,
  consultar,
  buscar,
  modificar,
  cancelar,
  finalizar,
  actualizarOcupacion,
};