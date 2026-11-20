const { test, before, after, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { randomUUID } = require('node:crypto');

const nombres = ['usuarios', 'vehiculos', 'viajes', 'reservas'];
const upstreams = {};
let gateway;
let puerto;

async function escuchar(servidor) {
  servidor.listen(0, '127.0.0.1');
  await new Promise((resolve, reject) => {
    servidor.once('listening', resolve);
    servidor.once('error', reject);
  });
  return servidor.address().port;
}

function request(method, path, { body, rawBody, headers = {} } = {}) {
  return new Promise((resolve, reject) => {
    const contenido = rawBody ?? (body === undefined ? undefined : JSON.stringify(body));
    const req = http.request({ hostname: '127.0.0.1', port: puerto, method, path,
      headers: { ...(contenido !== undefined ? { 'Content-Type': 'application/json' } : {}), ...headers },
    }, (res) => {
      let texto = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { texto += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers,
        texto, body: texto ? JSON.parse(texto) : undefined }));
    });
    req.on('error', reject);
    req.setTimeout(2500, () => req.destroy(new Error('El Gateway no terminó la solicitud de prueba')));
    req.end(contenido);
  });
}

before(async () => {
  for (const nombre of nombres) {
    const estado = { llamadas: [], readinessStatus: 200, readinessPayload: 'UP', modo: 'normal' };
    const servidor = http.createServer((req, res) => {
      if (req.url === '/health/ready') {
        estado.llamadas.push({ method: req.method, url: req.url, headers: req.headers });
        res.writeHead(estado.readinessStatus, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ status: estado.readinessPayload, servicio: nombre }));
      }
      if (estado.modo === 'reset') return req.socket.destroy();
      if (estado.modo === 'timeout') return;
      let rawBody = '';
      req.setEncoding('utf8');
      req.on('data', (chunk) => { rawBody += chunk; });
      req.on('end', () => {
        const llamada = { servicio: nombre, method: req.method, url: req.url, headers: req.headers, rawBody };
        estado.llamadas.push(llamada);
        if (nombre === 'vehiculos' && req.method === 'DELETE') {
          res.writeHead(204);
          return res.end();
        }
        res.writeHead(req.method === 'POST' ? 201 : 200, {
          'Content-Type': 'application/json', 'X-Correlation-Id': req.headers['x-correlation-id'],
          Location: `/api/v1/${nombre}/1`, ETag: '"3"',
        });
        return res.end(JSON.stringify(llamada));
      });
    });
    const port = await escuchar(servidor);
    upstreams[nombre] = { ...estado, servidor, port, estado };
  }
  Object.assign(process.env, {
    SERVER_HOST: '127.0.0.1', SERVER_PORT: '8080', FRONTEND_ORIGIN: 'http://localhost:5173,http://25.32.113.17:5173',
    GATEWAY_TIMEOUT_MS: '100', READINESS_TIMEOUT_MS: '200',
    USUARIOS_SERVICE_URL: `http://127.0.0.1:${upstreams.usuarios.port}`,
    VEHICULOS_SERVICE_URL: `http://127.0.0.1:${upstreams.vehiculos.port}`,
    VIAJES_SERVICE_URL: `http://127.0.0.1:${upstreams.viajes.port}`,
    RESERVAS_SERVICE_URL: `http://127.0.0.1:${upstreams.reservas.port}`,
  });
  const app = require('../src/app');
  gateway = http.createServer(app);
  puerto = await escuchar(gateway);
});

beforeEach(() => {
  for (const { estado } of Object.values(upstreams)) {
    estado.llamadas.length = 0;
    estado.readinessStatus = 200;
    estado.readinessPayload = 'UP';
    estado.modo = 'normal';
  }
});

after(async () => {
  await Promise.all([gateway, ...Object.values(upstreams).map((u) => u.servidor)].filter(Boolean).map(
    (servidor) => new Promise((resolve) => {
      servidor.close(resolve);
      servidor.closeAllConnections();
    })
  ));
});

test('cada prefijo conserva ruta y query y llega al servicio correspondiente', async () => {
  for (const [ruta, servicio] of [
    ['/api/v1/auth/login?retorno=%2Finicio', 'usuarios'],
    ['/api/v1/conductores/7?incluir=perfil', 'usuarios'],
    ['/api/v1/vehiculos?conductorId=7&pagina=2', 'vehiculos'],
    ['/api/v1/viajes?origen=San%20Jos%C3%A9&estado=TODOS', 'viajes'],
    ['/api/v1/reservas/viaje/305?estado=CONFIRMADA', 'reservas'],
    ['/api/v1/estadisticas/conductor/7?desde=2026-11-01', 'reservas'],
  ]) {
    const r = await request('GET', ruta);
    assert.equal(r.status, 200);
    assert.equal(r.body.servicio, servicio);
    assert.equal(r.body.url, ruta);
    assert.equal(r.body.method, 'GET');
  }
});

test('registro POST atraviesa el proxy con JSON completo sin consumir el stream', async () => {
  const rawBody = JSON.stringify({ nombre: 'María José', correo: 'prueba@example.test', password: 'clave-solo-test' });
  const r = await request('POST', '/api/v1/auth/registro', { rawBody });
  assert.equal(r.status, 201);
  assert.equal(r.body.url, '/api/v1/auth/registro');
  assert.equal(r.body.rawBody, rawBody);
  assert.deepEqual(JSON.parse(r.body.rawBody), JSON.parse(rawBody));
  assert.equal(r.headers.location, '/api/v1/usuarios/1');
});

test('proxy conserva Authorization, UUID, If-Match e Idempotency-Key', async () => {
  const cid = randomUUID();
  const r = await request('PATCH', '/api/v1/viajes/305', {
    body: { capacidad: 3 }, headers: { Authorization: 'Bearer jwt-solo-test', 'X-Correlation-Id': cid,
      'If-Match': '"3"', 'Idempotency-Key': 'intento-123' },
  });
  assert.equal(r.status, 200);
  assert.equal(r.body.headers.authorization, 'Bearer jwt-solo-test');
  assert.equal(r.body.headers['x-correlation-id'], cid);
  assert.equal(r.body.headers['if-match'], '"3"');
  assert.equal(r.body.headers['idempotency-key'], 'intento-123');
  assert.deepEqual(JSON.parse(r.body.rawBody), { capacidad: 3 });
  assert.equal(r.headers['x-correlation-id'], cid);
  assert.equal(r.headers.etag, '"3"');
});

test('UUID inválido se reemplaza y se propaga al upstream y al cliente', async () => {
  const r = await request('GET', '/api/v1/viajes/305', { headers: { 'X-Correlation-Id': 'arbitrario' } });
  assert.equal(r.status, 200);
  const cid = r.headers['x-correlation-id'];
  assert.match(cid, /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
  assert.equal(r.body.headers['x-correlation-id'], cid);
});

test('DELETE de vehículo conserva 204 y respuesta vacía', async () => {
  const r = await request('DELETE', '/api/v1/vehiculos/7', { headers: { Authorization: 'Bearer jwt-solo-test' } });
  assert.equal(r.status, 204);
  assert.equal(r.texto, '');
  assert.equal(upstreams.vehiculos.estado.llamadas[0].url, '/api/v1/vehiculos/7');
});

test('ocupación interna y rutas codificadas no se publican aunque llegue service key', async () => {
  for (const ruta of ['/api/v1/viajes/305/ocupacion', '/api/v1/viajes/305/ocupacion/?total=1',
    '/api/v1/viajes/305/%6f%63%75%70%61%63%69%6f%6e', '/api/v1/viajes/305%2Focupacion']) {
    const r = await request('PUT', ruta, { body: { cuposOcupados: 1 },
      headers: { 'X-Service-Key': 'llave-solo-test', Authorization: 'Bearer jwt-solo-test' } });
    assert.equal(r.status, 404, ruta);
    assert.equal(r.body.error, 'RUTA_NO_ENCONTRADA');
    assert.equal(r.body.correlationId, r.headers['x-correlation-id']);
  }
  assert.equal(upstreams.viajes.estado.llamadas.length, 0);
});

test('preflight CORS permite frontend y cabeceras de edición e idempotencia', async () => {
  const origen = 'http://localhost:5173';
  const r = await request('OPTIONS', '/api/v1/viajes/305', { headers: { Origin: origen,
    'Access-Control-Request-Method': 'PATCH',
    'Access-Control-Request-Headers': 'authorization,content-type,x-correlation-id,idempotency-key,if-match',
  } });
  assert.equal(r.status, 204);
  assert.equal(r.headers['access-control-allow-origin'], origen);
  assert.match(r.headers['access-control-allow-methods'], /PATCH/);
  const permitidas = r.headers['access-control-allow-headers'].toLowerCase().split(',').map((h) => h.trim());
  for (const h of ['authorization', 'content-type', 'x-correlation-id', 'idempotency-key', 'if-match']) {
    assert.ok(permitidas.includes(h), h);
  }
  assert.ok(!permitidas.includes('x-service-key'));
  assert.equal(upstreams.viajes.estado.llamadas.length, 0);
  const real = await request('GET', '/api/v1/viajes/305', { headers: { Origin: origen } });
  assert.equal(real.headers['access-control-allow-origin'], origen);
  for (const h of ['X-Correlation-Id', 'Location', 'ETag']) {
    assert.ok(real.headers['access-control-expose-headers'].includes(h));
  }
});

test('origen ajeno no recibe permiso CORS y prefijos parecidos no se enrutan', async () => {
  const r = await request('GET', '/api/v1/viajes/305', { headers: { Origin: 'http://ajeno.example.test' } });
  assert.equal(r.headers['access-control-allow-origin'], undefined);
  const desconocida = await request('GET', '/api/v1/viajes-ajenos?token=valor-no-exponer');
  assert.equal(desconocida.status, 404);
  assert.equal(desconocida.body.path, '/api/v1/viajes-ajenos');
  assert.doesNotMatch(JSON.stringify(desconocida.body), /valor-no-exponer/);
});

test('readiness agrega cuatro dependencias UP y propaga UUID', async () => {
  const cid = randomUUID();
  const r = await request('GET', '/health/ready', { headers: { 'X-Correlation-Id': cid } });
  assert.equal(r.status, 200);
  assert.deepEqual(r.body, { status: 'UP', servicio: 'api-gateway',
    servicios: { usuarios: 'UP', vehiculos: 'UP', viajes: 'UP', reservas: 'UP' } });
  for (const nombre of nombres) {
    assert.equal(upstreams[nombre].estado.llamadas[0].url, '/health/ready');
    assert.equal(upstreams[nombre].estado.llamadas[0].headers['x-correlation-id'], cid);
  }
});

test('readiness devuelve 503 con HTTP 200 pero payload DOWN; liveness sigue UP', async () => {
  upstreams.vehiculos.estado.readinessPayload = 'DOWN';
  const r = await request('GET', '/health/ready');
  assert.equal(r.status, 503);
  assert.equal(r.body.status, 'DOWN');
  assert.equal(r.body.servicios.vehiculos, 'DOWN');
  assert.equal(r.body.servicios.viajes, 'UP');
  assert.equal((await request('GET', '/health')).status, 200);
});

test('readiness rechaza una dependencia HTTP 503 aunque su payload diga UP', async () => {
  upstreams.reservas.estado.readinessStatus = 503;
  const r = await request('GET', '/health/ready');
  assert.equal(r.status, 503);
  assert.equal(r.body.servicios.reservas, 'DOWN');
});

test('fallo inmediato de upstream produce 503 con error sanitizado', async () => {
  upstreams.viajes.estado.modo = 'reset';
  const r = await request('GET', '/api/v1/viajes/305');
  assert.equal(r.status, 503);
  assert.equal(r.body.error, 'SERVICIO_DEPENDIENTE_NO_DISPONIBLE');
  assert.equal(r.body.path, '/api/v1/viajes/305');
  assert.equal(r.body.correlationId, r.headers['x-correlation-id']);
  assert.doesNotMatch(JSON.stringify(r.body), /127\.0\.0\.1|ECONNRESET|stack/);
});

test('upstream que no responde produce 504 con presupuesto acotado', async () => {
  upstreams.viajes.estado.modo = 'timeout';
  const inicio = Date.now();
  const r = await request('GET', '/api/v1/viajes/305');
  assert.equal(r.status, 504);
  assert.equal(r.body.error, 'TIEMPO_DE_ESPERA_AGOTADO');
  assert.ok(Date.now() - inicio < 2000);
  assert.equal(r.body.correlationId, r.headers['x-correlation-id']);
});
