const { AppError } = require('./errores');

const MAX_INT = 2147483647;
const ESTADOS_BUSQUEDA = ['ACTIVO', 'CANCELADO', 'FINALIZADO', 'TODOS'];

// ---------- Utilidades básicas ----------

const esObjeto = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const esEnteroPositivo = (v) => Number.isInteger(v) && v > 0 && v <= MAX_INT;

function esFechaValida(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const [y, m, d] = s.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return (
    dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d
  );
}

const esHoraValida = (s) =>
  typeof s === 'string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(s);

// Acumula errores de campo y lanza un único 400 con "detalles"
class Validador {
  constructor() {
    this.detalles = [];
  }

  agregar(campo, problema, codigo = 'FORMATO_INVALIDO') {
    this.detalles.push({ campo, problema, codigo });
  }

  lanzarSiHayErrores() {
    if (this.detalles.length === 0) return;
    const codigos = [...new Set(this.detalles.map((d) => d.codigo))];
    const error = codigos.length === 1 ? codigos[0] : 'SOLICITUD_INVALIDA';
    const detalles = this.detalles.map(({ campo, problema }) => ({ campo, problema }));
    throw new AppError(400, error, 'La solicitud contiene datos inválidos.', detalles);
  }
}

// ---------- Validadores por campo (devuelven el valor limpio o undefined) ----------

function validarPunto(v, campo, val) {
  if (!esObjeto(v)) {
    val.agregar(campo, 'Debe ser un objeto con descripcion, latitud y longitud');
    return undefined;
  }
  let ok = true;
  if (typeof v.descripcion !== 'string' || v.descripcion.trim() === '') {
    val.agregar(`${campo}.descripcion`, 'Debe ser un texto no vacío');
    ok = false;
  }
  if (typeof v.latitud !== 'number' || !(v.latitud >= -90 && v.latitud <= 90)) {
    val.agregar(`${campo}.latitud`, 'Debe ser un número entre -90 y 90');
    ok = false;
  }
  if (typeof v.longitud !== 'number' || !(v.longitud >= -180 && v.longitud <= 180)) {
    val.agregar(`${campo}.longitud`, 'Debe ser un número entre -180 y 180');
    ok = false;
  }
  return ok
    ? { descripcion: v.descripcion.trim(), latitud: v.latitud, longitud: v.longitud }
    : undefined;
}

const validadores = {
  vehiculoId: (v, val) => {
    if (esEnteroPositivo(v)) return v;
    val.agregar('vehiculoId', 'Debe ser un entero positivo');
    return undefined;
  },
  origen: (v, val) => validarPunto(v, 'origen', val),
  destino: (v, val) => validarPunto(v, 'destino', val),
  fechaSalida: (v, val) => {
    if (esFechaValida(v)) return v;
    val.agregar('fechaSalida', 'Debe tener formato YYYY-MM-DD y ser una fecha real', 'FECHA_HORA_INVALIDA');
    return undefined;
  },
  horaSalida: (v, val) => {
    if (esHoraValida(v)) return v;
    val.agregar('horaSalida', 'Debe tener formato HH:MM (24 horas)', 'FECHA_HORA_INVALIDA');
    return undefined;
  },
  capacidad: (v, val) => {
    if (Number.isInteger(v) && v >= 1 && v <= 8) return v;
    val.agregar('capacidad', 'Debe estar entre 1 y 8', 'CAPACIDAD_INVALIDA');
    return undefined;
  },
};

const CAMPOS_VIAJE = ['vehiculoId', 'origen', 'destino', 'fechaSalida', 'horaSalida', 'capacidad'];

// ---------- Validaciones por endpoint ----------

function validarCrearViaje(body) {
  if (!esObjeto(body)) {
    throw new AppError(400, 'SOLICITUD_INVALIDA', 'El cuerpo debe ser un objeto JSON.');
  }
  const val = new Validador();
  const datos = {};
  for (const campo of CAMPOS_VIAJE) {
    if (body[campo] === undefined || body[campo] === null) {
      val.agregar(campo, 'Es obligatorio', 'CAMPO_OBLIGATORIO_FALTANTE');
    } else {
      datos[campo] = validadores[campo](body[campo], val);
    }
  }
  val.lanzarSiHayErrores();
  return datos;
}

function validarActualizarViaje(body) {
  if (!esObjeto(body)) {
    throw new AppError(400, 'SOLICITUD_INVALIDA', 'El cuerpo debe ser un objeto JSON.');
  }
  const presentes = CAMPOS_VIAJE.filter((c) => body[c] !== undefined);
  if (presentes.length === 0) {
    throw new AppError(
      400,
      'SOLICITUD_INVALIDA',
      `Debe enviar al menos uno de: ${CAMPOS_VIAJE.join(', ')}.`,
      [{ campo: 'body', problema: 'No se envió ningún campo modificable' }]
    );
  }
  const val = new Validador();
  const datos = {};
  for (const campo of presentes) {
    datos[campo] = validadores[campo](body[campo], val);
  }
  val.lanzarSiHayErrores();
  return datos;
}

function validarOcupacion(body) {
  if (!esObjeto(body)) {
    throw new AppError(400, 'SOLICITUD_INVALIDA', 'El cuerpo debe ser un objeto JSON.');
  }
  const val = new Validador();
  if (body.cuposOcupados === undefined || body.cuposOcupados === null) {
    val.agregar('cuposOcupados', 'Es obligatorio', 'CAMPO_OBLIGATORIO_FALTANTE');
  } else if (!Number.isInteger(body.cuposOcupados) || body.cuposOcupados < 0) {
    val.agregar('cuposOcupados', 'Debe ser un entero mayor o igual a 0');
  }
  val.lanzarSiHayErrores();
  return { cuposOcupados: body.cuposOcupados };
}

function validarFiltros(q) {
  const val = new Validador();

  const texto = (n) => {
    const v = q[n];
    if (v === undefined) return undefined;
    if (typeof v !== 'string' || v.trim() === '') {
      val.agregar(n, 'Valor inválido');
      return undefined;
    }
    return v.trim();
  };
  const entero = (n) => {
    const v = texto(n);
    if (v === undefined) return undefined;
    if (!/^\d+$/.test(v) || Number(v) < 1 || Number(v) > MAX_INT) {
      val.agregar(n, 'Debe ser un entero positivo');
      return undefined;
    }
    return Number(v);
  };
  const decimal = (n, min, max) => {
    const v = texto(n);
    if (v === undefined) return undefined;
    const x = Number(v);
    if (!Number.isFinite(x) || x < min || x > max) {
      val.agregar(n, `Debe ser un número entre ${min} y ${max}`);
      return undefined;
    }
    return x;
  };
  const fecha = (n) => {
    const v = texto(n);
    if (v === undefined) return undefined;
    if (!esFechaValida(v)) {
      val.agregar(n, 'Debe tener formato YYYY-MM-DD', 'FECHA_HORA_INVALIDA');
      return undefined;
    }
    return v;
  };
  const hora = (n) => {
    const v = texto(n);
    if (v === undefined) return undefined;
    if (!esHoraValida(v)) {
      val.agregar(n, 'Debe tener formato HH:MM', 'FECHA_HORA_INVALIDA');
      return undefined;
    }
    return v;
  };
  const geo = (prefijo) => {
    const nombres = [`${prefijo}Lat`, `${prefijo}Lon`, `${prefijo}RadioKm`];
    if (nombres.every((n) => q[n] === undefined)) return null;
    const faltan = nombres.filter((n) => q[n] === undefined);
    faltan.forEach((n) =>
      val.agregar(n, 'Es obligatorio junto con los demás parámetros de ubicación', 'CAMPO_OBLIGATORIO_FALTANTE')
    );
    const lat = decimal(nombres[0], -90, 90);
    const lon = decimal(nombres[1], -180, 180);
    const radioKm = decimal(nombres[2], 0, 20000);
    if (faltan.length > 0 || lat === undefined || lon === undefined || radioKm === undefined) {
      return null;
    }
    return { lat, lon, radioKm };
  };

  const filtros = {
    fecha: fecha('fecha'),
    horaDesde: hora('horaDesde'),
    horaHasta: hora('horaHasta'),
    origen: geo('origen'),
    destino: geo('destino'),
    conductorId: entero('conductorId'),
    vehiculoId: entero('vehiculoId'),
    desde: fecha('desde'),
    hasta: fecha('hasta'),
    estado: 'ACTIVO',
    disponibles: false,
    pagina: 1,
    tamano: 20,
  };

  const disp = texto('disponibles');
  if (disp !== undefined) {
    if (disp !== 'true' && disp !== 'false') {
      val.agregar('disponibles', 'Debe ser true o false');
    } else {
      filtros.disponibles = disp === 'true';
    }
  }

  const est = texto('estado');
  if (est !== undefined) {
    if (!ESTADOS_BUSQUEDA.includes(est)) {
      val.agregar('estado', 'Debe ser ACTIVO, CANCELADO, FINALIZADO o TODOS');
    } else {
      filtros.estado = est;
    }
  }

  const pagina = entero('pagina');
  if (pagina !== undefined) filtros.pagina = pagina;

  const tamano = entero('tamano');
  if (tamano !== undefined) {
    if (tamano > 50) val.agregar('tamano', 'El máximo es 50');
    else filtros.tamano = tamano;
  }

  if (filtros.desde && filtros.hasta && filtros.desde > filtros.hasta) {
    val.agregar('desde', 'No puede ser mayor que hasta', 'FECHA_HORA_INVALIDA');
  }
  if (filtros.horaDesde && filtros.horaHasta && filtros.horaDesde > filtros.horaHasta) {
    val.agregar('horaDesde', 'No puede ser mayor que horaHasta', 'FECHA_HORA_INVALIDA');
  }

  val.lanzarSiHayErrores();
  return filtros;
}

// ---------- Parámetros de ruta y headers ----------

function leerIdRuta(valor, nombre) {
  if (!/^\d+$/.test(valor) || Number(valor) < 1 || Number(valor) > MAX_INT) {
    throw new AppError(400, 'FORMATO_INVALIDO', `${nombre} debe ser un entero positivo.`, [
      { campo: nombre, problema: 'Debe ser un entero positivo' },
    ]);
  }
  return Number(valor);
}

function leerIfMatch(req) {
  const crudo = req.get('If-Match');
  if (crudo === undefined) return undefined;
  const limpio = crudo.trim().replace(/^W\//, '').replace(/^"|"$/g, '');
  if (!/^\d+$/.test(limpio)) {
    throw new AppError(400, 'FORMATO_INVALIDO', 'If-Match debe contener el valor de version.', [
      { campo: 'If-Match', problema: 'Debe ser un entero' },
    ]);
  }
  return Number(limpio);
}

function leerIdempotencyKey(req) {
  const clave = req.get('Idempotency-Key');
  if (clave === undefined) return undefined;
  const limpia = clave.trim();
  if (limpia === '' || limpia.length > 100) {
    throw new AppError(400, 'FORMATO_INVALIDO', 'Idempotency-Key debe tener entre 1 y 100 caracteres.', [
      { campo: 'Idempotency-Key', problema: 'Longitud inválida' },
    ]);
  }
  return limpia;
}

module.exports = {
  validarCrearViaje,
  validarActualizarViaje,
  validarOcupacion,
  validarFiltros,
  leerIdRuta,
  leerIfMatch,
  leerIdempotencyKey,
};