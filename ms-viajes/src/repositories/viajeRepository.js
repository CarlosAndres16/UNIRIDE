const pool = require('../config/db');

const COLUMNAS_ACTUALIZABLES = new Set([
  'vehiculo_id',
  'origen_descripcion',
  'origen_latitud',
  'origen_longitud',
  'destino_descripcion',
  'destino_latitud',
  'destino_longitud',
  'fecha_salida',
  'hora_salida',
  'capacidad',
]);

async function crear(d) {
  const { rows } = await pool.query(
    `INSERT INTO viajes
       (conductor_id, vehiculo_id,
        origen_descripcion, origen_latitud, origen_longitud,
        destino_descripcion, destino_latitud, destino_longitud,
        fecha_salida, hora_salida, capacidad, idempotency_key)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
     RETURNING *`,
    [
      d.conductorId,
      d.vehiculoId,
      d.origen.descripcion,
      d.origen.latitud,
      d.origen.longitud,
      d.destino.descripcion,
      d.destino.latitud,
      d.destino.longitud,
      d.fechaSalida,
      d.horaSalida,
      d.capacidad,
      d.idempotencyKey,
    ]
  );
  return rows[0];
}

async function buscarPorId(id) {
  const { rows } = await pool.query('SELECT * FROM viajes WHERE id = $1', [id]);
  return rows[0] || null;
}

async function buscarPorIdempotencia(conductorId, clave) {
  const { rows } = await pool.query(
    'SELECT * FROM viajes WHERE conductor_id = $1 AND idempotency_key = $2',
    [conductorId, clave]
  );
  return rows[0] || null;
}

async function existeDuplicado(conductorId, vehiculoId, fecha, hora) {
  const { rows } = await pool.query(
    `SELECT 1 FROM viajes
      WHERE conductor_id = $1 AND vehiculo_id = $2
        AND fecha_salida = $3::date AND hora_salida = $4::time
        AND estado = 'ACTIVO'
      LIMIT 1`,
    [conductorId, vehiculoId, fecha, hora]
  );
  return rows.length > 0;
}

// Distancia de Haversine en km entre (prefijo_latitud, prefijo_longitud) y un punto
function haversine(prefijo, lat, lon, radio) {
  return `(2 * 6371 * asin(sqrt(least(1,
    power(sin(radians(${prefijo}_latitud - ${lat}::float8) / 2), 2) +
    cos(radians(${lat}::float8)) * cos(radians(${prefijo}_latitud)) *
    power(sin(radians(${prefijo}_longitud - ${lon}::float8) / 2), 2)
  )))) <= ${radio}::float8`;
}

async function buscar(f) {
  const params = [];
  const cond = [];
  const p = (valor) => {
    params.push(valor);
    return `$${params.length}`;
  };

  if (f.estado !== 'TODOS') cond.push(`estado = ${p(f.estado)}`);
  if (f.fecha) cond.push(`fecha_salida = ${p(f.fecha)}::date`);
  if (f.horaDesde) cond.push(`hora_salida >= ${p(f.horaDesde)}::time`);
  if (f.horaHasta) cond.push(`hora_salida <= ${p(f.horaHasta)}::time`);
  if (f.desde) cond.push(`fecha_salida >= ${p(f.desde)}::date`);
  if (f.hasta) cond.push(`fecha_salida <= ${p(f.hasta)}::date`);
  if (f.conductorId) cond.push(`conductor_id = ${p(f.conductorId)}`);
  if (f.vehiculoId) cond.push(`vehiculo_id = ${p(f.vehiculoId)}`);
  if (f.disponibles) cond.push('(capacidad - cupos_ocupados) > 0');
  if (f.origen) {
    cond.push(haversine('origen', p(f.origen.lat), p(f.origen.lon), p(f.origen.radioKm)));
  }
  if (f.destino) {
    cond.push(haversine('destino', p(f.destino.lat), p(f.destino.lon), p(f.destino.radioKm)));
  }

  const where = cond.length > 0 ? `WHERE ${cond.join(' AND ')}` : '';

  const conteo = await pool.query(`SELECT COUNT(*) AS total FROM viajes ${where}`, params);
  const total = Number(conteo.rows[0].total);

  const paramsDatos = [...params, f.tamano, (f.pagina - 1) * f.tamano];
  const { rows } = await pool.query(
    `SELECT * FROM viajes ${where}
      ORDER BY fecha_salida, hora_salida, id
      LIMIT $${params.length + 1} OFFSET $${params.length + 2}`,
    paramsDatos
  );

  return { filas: rows, total };
}

// Actualiza solo si la versión coincide y el viaje sigue ACTIVO (bloqueo optimista)
async function actualizar(id, versionActual, cambios) {
  const params = [id, versionActual];
  const sets = [];
  for (const [columna, valor] of Object.entries(cambios)) {
    if (!COLUMNAS_ACTUALIZABLES.has(columna)) {
      throw new Error(`Columna no permitida: ${columna}`);
    }
    params.push(valor);
    sets.push(`${columna} = $${params.length}`);
  }
  sets.push('version = version + 1', 'fecha_actualizacion = now()');

  const { rows } = await pool.query(
    `UPDATE viajes SET ${sets.join(', ')}
      WHERE id = $1 AND version = $2 AND estado = 'ACTIVO'
      RETURNING *`,
    params
  );
  return rows[0] || null;
}

// Cancelar o finalizar: solo desde ACTIVO
async function cambiarEstado(id, nuevoEstado) {
  const { rows } = await pool.query(
    `UPDATE viajes
        SET estado = $2, version = version + 1, fecha_actualizacion = now()
      WHERE id = $1 AND estado = 'ACTIVO'
      RETURNING *`,
    [id, nuevoEstado]
  );
  return rows[0] || null;
}

// Idempotente: recibe el total; repetirlo no cambia nada (ni version ni fecha)
async function actualizarOcupacion(id, cuposOcupados) {
  const { rows } = await pool.query(
    `UPDATE viajes
        SET fecha_actualizacion = CASE WHEN cupos_ocupados <> $2::integer
                                       THEN now() ELSE fecha_actualizacion END,
            cupos_ocupados = $2::integer
      WHERE id = $1 AND estado = 'ACTIVO'
      RETURNING *`,
    [id, cuposOcupados]
  );
  return rows[0] || null;
}

module.exports = {
  crear,
  buscarPorId,
  buscarPorIdempotencia,
  existeDuplicado,
  buscar,
  actualizar,
  cambiarEstado,
  actualizarOcupacion,
};