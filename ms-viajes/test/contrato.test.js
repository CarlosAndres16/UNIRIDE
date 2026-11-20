const { test, before, after, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { createHmac, randomUUID } = require('node:crypto');

// Valores exclusivos de tests; no se requiere ni se escribe un archivo .env.
Object.assign(process.env, {
  SERVER_PORT: '8083', DB_HOST: '127.0.0.1', DB_PORT: '5432', DB_NAME: 'test',
  DB_USER: 'test', DB_PASSWORD: 'test-only', JWT_SECRET: 'test-only-jwt-secret',
  SERVICE_API_KEY: 'test-only-service-key', VEHICULOS_SERVICE_URL: 'http://127.0.0.1:8082',
  HTTP_TIMEOUT_MS: '50', HTTP_MAX_RETRIES: '1',
});
const app = require('../src/app');
const repo = require('../src/repositories/viajeRepository');
const pool = require('../src/config/db');
const { obtenerVehiculo } = require('../src/clients/vehiculosClient');
const { validarOcupacion, leerIfMatch } = require('../src/utils/validaciones');
const originalRepo = { ...repo };
const originalQuery = pool.query;
const originalFetch = global.fetch;
let server;
let port;
let filas;

function token(sub = '7', claims = {}, algorithm = 'HS256', secret = process.env.JWT_SECRET) {
  const now = Math.floor(Date.now() / 1000);
  const b64 = (v) => Buffer.from(JSON.stringify(v)).toString('base64url');
  const data = `${b64({ alg: algorithm, typ: 'JWT' })}.${b64({ sub, iat: now, exp: now + 3600, ...claims })}`;
  return `${data}.${createHmac(algorithm === 'HS384' ? 'sha384' : 'sha256', secret).update(data).digest('base64url')}`;
}

const datos = {
  vehiculoId: 3, origen: { descripcion: 'Universidad', latitud: 4.6, longitud: -74.1 },
  destino: { descripcion: 'Centro', latitud: 4.5, longitud: -74.0 },
  fechaSalida: '2026-12-01', horaSalida: '08:00', capacidad: 4,
};
function fila(id = 1, conductorId = 7) {
  return {
    id, conductor_id: conductorId, vehiculo_id: datos.vehiculoId,
    origen_descripcion: datos.origen.descripcion, origen_latitud: 4.6, origen_longitud: -74.1,
    destino_descripcion: datos.destino.descripcion, destino_latitud: 4.5, destino_longitud: -74,
    fecha_salida: datos.fechaSalida, hora_salida: '08:00:00', capacidad: 4, cupos_ocupados: 0,
    estado: 'ACTIVO', version: 1,
    fecha_creacion: '2026-11-01T12:00:00Z', fecha_actualizacion: '2026-11-01T12:00:00Z',
  };
}
const vehiculo = { vehiculoId: 3, conductorId: 7, capacidad: 4, estado: 'ACTIVO' };
const respuestaVehiculo = (cuerpo = vehiculo, status = 200) => ({ status, json: async () => cuerpo });

function request(method, path, { body, headers = {}, auth = true } = {}) {
  return new Promise((resolve, reject) => {
    const contenido = body === undefined ? undefined : JSON.stringify(body);
    const req = http.request({
      hostname: '127.0.0.1', port, method, path,
      headers: { ...(auth ? { Authorization: `Bearer ${token()}` } : {}),
        ...(contenido ? { 'Content-Type': 'application/json' } : {}), ...headers },
    }, (res) => {
      let texto = '';
      res.setEncoding('utf8');
      res.on('data', (d) => { texto += d; });
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers,
        body: texto ? JSON.parse(texto) : undefined }));
    });
    req.on('error', reject);
    req.end(contenido);
  });
}

before(async () => {
  server = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  port = server.address().port;
});
after(async () => {
  await new Promise((resolve) => server.close(resolve));
  await pool.end();
});
beforeEach(() => {
  filas = [fila(), fila(2, 8)];
  repo.buscarPorId = async (id) => filas.find((v) => v.id === id) || null;
  repo.buscar = async (f) => {
    const propias = filas.filter((v) => v.conductor_id === f.conductorId);
    return { filas: propias, total: propias.length };
  };
  repo.buscarPorIdempotencia = async () => null;
  repo.existeDuplicado = async () => false;
  repo.crear = async (d) => ({ ...fila(3, d.conductorId), capacidad: d.capacidad });
  global.fetch = async () => respuestaVehiculo();
  pool.query = async () => ({ rows: [{ '?column?': 1 }] });
});
afterEach(() => {
  Object.assign(repo, originalRepo);
  pool.query = originalQuery;
  global.fetch = originalFetch;
});

test('GET detalle exige JWT y propietario; no expone el viaje ajeno', async () => {
  assert.equal((await request('GET', '/api/v1/viajes/1', { auth: false })).status, 401);
  assert.equal((await request('GET', '/api/v1/viajes/1')).body.conductorId, 7);
  const ajeno = await request('GET', '/api/v1/viajes/2');
  assert.equal(ajeno.status, 403);
  assert.equal(ajeno.body.error, 'NO_AUTORIZADO');
  assert.equal(ajeno.body.vehiculoId, undefined);
  assert.equal((await request('GET', '/api/v1/viajes/99')).status, 404);
  assert.equal((await request('GET', '/api/v1/viajes/2147483648')).status, 400);
});

test('GET lista fuerza el conductor del JWT y rechaza filtros ajenos', async () => {
  const propia = await request('GET', '/api/v1/viajes?estado=TODOS');
  assert.equal(propia.status, 200);
  assert.deepEqual(propia.body.datos.map((v) => v.conductorId), [7]);
  assert.equal(propia.body.paginacion.totalElementos, 1);
  repo.buscar = async () => { throw new Error('No debe consultar un filtro ajeno'); };
  assert.equal((await request('GET', '/api/v1/viajes?conductorId=8')).status, 403);
});

test('JWT requiere HS256, sub textual SQL int positivo e iat/exp enteros', async () => {
  const now = Math.floor(Date.now() / 1000);
  const invalidos = [
    token(7), token('0'), token('-1'), token('1.0'), token('1e2'), token(' 7 '),
    token('2147483648'), token('7', { iat: undefined }), token('7', { exp: undefined }),
    token('7', { iat: now + 0.5 }), token('7', { exp: now + 3600.5 }),
    token('7', { iat: now + 7200, exp: now + 3600 }), token('7', { exp: now - 1 }),
    token('7', {}, 'HS384'), token('7', {}, 'HS256', 'otra-clave'),
  ];
  for (const t of invalidos) {
    const r = await request('GET', '/api/v1/viajes/1', { headers: { Authorization: `Bearer ${t}` } });
    assert.equal(r.status, 401);
    assert.equal(r.body.error, 'NO_AUTENTICADO');
  }
  const valido = await request('GET', '/api/v1/viajes/1', { headers: { Authorization: `bearer ${token()}` } });
  assert.equal(valido.status, 200);
});

test('correlación reutiliza UUID válido y regenera valores arbitrarios en errores', async () => {
  const cid = randomUUID();
  const r = await request('GET', '/api/v1/viajes/2', { headers: { 'X-Correlation-Id': cid } });
  assert.equal(r.headers['x-correlation-id'], cid);
  assert.equal(r.body.correlationId, cid);
  const generado = await request('GET', '/no-existe', { headers: { 'X-Correlation-Id': 'texto-arbitrario' } });
  assert.match(generado.body.correlationId, /^[0-9a-f-]{36}$/);
  assert.notEqual(generado.body.correlationId, 'texto-arbitrario');
});

test('crear reenvía JWT/UUID, ignora conductor del body y respeta capacidad de Vehículos', async () => {
  const cid = randomUUID();
  const jwtEnviado = token();
  let llamada;
  global.fetch = async (url, opciones) => { llamada = { url, opciones }; return respuestaVehiculo(); };
  const r = await request('POST', '/api/v1/viajes', { body: { ...datos, conductorId: 8 },
    headers: { 'X-Correlation-Id': cid, Authorization: `Bearer ${jwtEnviado}` } });
  assert.equal(r.status, 201);
  assert.equal(r.body.conductorId, 7);
  assert.equal(r.headers.location, '/api/v1/viajes/3');
  assert.equal(llamada.url, 'http://127.0.0.1:8082/api/v1/vehiculos/3');
  assert.equal(llamada.opciones.headers.Authorization, `Bearer ${jwtEnviado}`);
  assert.equal(llamada.opciones.headers['X-Correlation-Id'], cid);
  assert.equal((await request('POST', '/api/v1/viajes', { body: { ...datos, capacidad: 5 } })).status, 400);
  global.fetch = async () => respuestaVehiculo({ ...vehiculo, estado: 'INACTIVO' });
  assert.equal((await request('POST', '/api/v1/viajes', { body: datos })).status, 409);
});

test('cliente valida DTO, id solicitado y propietario y reintenta solo fallos de dependencia', async () => {
  const ctx = { token: token(), conductorId: 7, correlationId: randomUUID() };
  for (const malformado of [null, [], { ...vehiculo, vehiculoId: 4 },
    { ...vehiculo, conductorId: 0 }, { ...vehiculo, capacidad: 0 },
    { ...vehiculo, capacidad: 2147483648 }, { ...vehiculo, estado: 'DESCONOCIDO' }]) {
    let intentos = 0;
    global.fetch = async () => { intentos++; return respuestaVehiculo(malformado); };
    await assert.rejects(obtenerVehiculo(3, ctx), (e) => e.status === 503);
    assert.equal(intentos, 2);
  }
  global.fetch = async () => respuestaVehiculo({ ...vehiculo, conductorId: 8 });
  await assert.rejects(obtenerVehiculo(3, ctx), (e) => e.status === 403);
  for (const status of [401, 403, 404]) {
    let intentos = 0;
    global.fetch = async () => { intentos++; return respuestaVehiculo(undefined, status); };
    await assert.rejects(obtenerVehiculo(3, ctx), (e) => e.status === status);
    assert.equal(intentos, 1);
  }
  let intentos = 0;
  global.fetch = async () => { intentos++; throw new Error('timeout de prueba'); };
  await assert.rejects(obtenerVehiculo(3, ctx), (e) => e.status === 503);
  assert.equal(intentos, 2);
});

test('Idempotency-Key reutiliza resultado sin crear ni consultar Vehículos de nuevo', async () => {
  repo.buscarPorIdempotencia = async (conductorId, clave) => {
    assert.equal(conductorId, 7);
    assert.equal(clave, 'intento-1');
    return fila();
  };
  repo.crear = async () => { throw new Error('No debe duplicar'); };
  global.fetch = async () => { throw new Error('No debe consultar proveedor'); };
  const r = await request('POST', '/api/v1/viajes', { body: datos, headers: { 'Idempotency-Key': 'intento-1' } });
  assert.equal(r.status, 201);
  assert.equal(r.body.viajeId, 1);
});

test('Idempotency-Key recupera el resultado de una creación concurrente', async () => {
  let lecturas = 0;
  repo.buscarPorIdempotencia = async () => (++lecturas === 1 ? null : fila());
  repo.existeDuplicado = async () => true;
  repo.crear = async () => { throw new Error('No debe duplicar'); };
  const r = await request('POST', '/api/v1/viajes', { body: datos, headers: { 'Idempotency-Key': 'carrera-1' } });
  assert.equal(r.status, 201);
  assert.equal(r.body.viajeId, 1);
});

test('PATCH protege ownership, versión y capacidad frente a reservas/vehículo', async () => {
  assert.equal((await request('PATCH', '/api/v1/viajes/2', { body: { capacidad: 3 } })).status, 403);
  assert.equal((await request('PATCH', '/api/v1/viajes/1', { body: { capacidad: 3 }, headers: { 'If-Match': '9' } })).status, 409);
  assert.equal((await request('PATCH', '/api/v1/viajes/1', { body: { capacidad: 5 } })).status, 400);
  filas[0].cupos_ocupados = 3;
  assert.equal((await request('PATCH', '/api/v1/viajes/1', { body: { capacidad: 2 } })).status, 409);
  repo.actualizar = async () => null; // otra petición cambió la versión tras la lectura
  assert.equal((await request('PATCH', '/api/v1/viajes/1', { body: { capacidad: 4 } })).status, 409);
});

test('ocupación exige SERVICE_API_KEY, acepta total absoluto e impide exceder capacidad', async () => {
  const path = '/api/v1/viajes/1/ocupacion';
  assert.equal((await request('PUT', path, { body: { cuposOcupados: 1 } })).status, 401);
  const opciones = { auth: false, headers: { 'X-Service-Key': process.env.SERVICE_API_KEY } };
  let total;
  repo.actualizarOcupacion = async (id, valor) => { total = valor; return { ...fila(id), cupos_ocupados: valor }; };
  for (let i = 0; i < 2; i++) {
    const r = await request('PUT', path, { ...opciones, body: { cuposOcupados: 2 } });
    assert.equal(r.status, 200);
    assert.equal(r.body.cuposDisponibles, 2);
    assert.equal(total, 2);
  }
  assert.equal((await request('PUT', path, { ...opciones, body: { cuposOcupados: 5 } })).status, 400);
  assert.equal((await request('PUT', path, { ...opciones, body: { cuposOcupados: -1 } })).status, 400);
  repo.actualizarOcupacion = async () => null; // la capacidad cambió entre SELECT y UPDATE
  assert.equal((await request('PUT', path, { ...opciones, body: { cuposOcupados: 2 } })).status, 409);
});

test('repositorio impone límite de ocupación y avanza versión solo cuando cambia el total', async () => {
  let consulta;
  pool.query = async (sql, params) => { consulta = { sql, params }; return { rows: [fila()] }; };
  await originalRepo.actualizarOcupacion(1, 2);
  assert.deepEqual(consulta.params, [1, 2]);
  assert.match(consulta.sql, /\$2::integer BETWEEN 0 AND capacidad/);
  assert.match(consulta.sql, /version = CASE WHEN cupos_ocupados <> \$2::integer THEN version \+ 1 ELSE version END/);
  await originalRepo.actualizar(1, 3, { capacidad: 4 });
  assert.match(consulta.sql, /version = \$2 AND estado = 'ACTIVO'/);
  assert.deepEqual(consulta.params, [1, 3, 4]);
});

test('health de proceso y readiness independientes; fallos DB devuelven 503 sin detalles', async () => {
  pool.query = async () => { throw new Error('password=secret host=privado'); };
  assert.equal((await request('GET', '/health', { auth: false })).status, 200);
  const down = await request('GET', '/health/ready', { auth: false });
  assert.equal(down.status, 503);
  assert.deepEqual(down.body, { status: 'DOWN', servicio: 'ms-viajes', database: 'DOWN' });
  pool.query = async (sql) => { assert.equal(sql, 'SELECT 1'); return { rows: [] }; };
  const up = await request('GET', '/health/ready', { auth: false });
  assert.equal(up.status, 200);
  assert.deepEqual(up.body, { status: 'UP', servicio: 'ms-viajes', database: 'UP' });
});

test('fallos internos conservan el formato de error sin exponer credenciales', async () => {
  repo.buscarPorId = async () => { throw new Error('password=no-debe-aparecer'); };
  const r = await request('GET', '/api/v1/viajes/1');
  assert.equal(r.status, 500);
  assert.equal(r.body.error, 'ERROR_INTERNO');
  assert.equal(r.body.path, '/api/v1/viajes/1');
  assert.equal(r.body.correlationId, r.headers['x-correlation-id']);
  assert.doesNotMatch(JSON.stringify(r.body), /password|no-debe-aparecer/);
});

test('validación limita enteros SQL para ocupación e If-Match', () => {
  assert.throws(() => validarOcupacion({ cuposOcupados: 2147483648 }), (e) => e.status === 400);
  assert.throws(() => leerIfMatch({ get: () => '99999999999999999999999' }), (e) => e.status === 400);
  assert.equal(leerIfMatch({ get: () => '"2"' }), 2);
});
