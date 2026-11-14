import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError, query, request } from '../src/lib/http.ts';

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

test('envía JSON, Bearer y un UUID distinto por solicitud', async t => {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, options });
    return Response.json({ vehiculoId: 8 }, { status: 201 });
  });
  const options = { method: 'POST', token: 'token-ficticio-para-prueba', body: { placa: 'ABC123' } };
  assert.deepEqual(await request('http://gateway.test/api/v1/', '/vehiculos', options), { vehiculoId: 8 });
  await request('http://gateway.test/api/v1', '/vehiculos', options);
  assert.equal(calls[0].url, 'http://gateway.test/api/v1/vehiculos');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer token-ficticio-para-prueba');
  assert.equal(calls[0].options.headers['Content-Type'], 'application/json');
  assert.equal(calls[0].options.body, '{"placa":"ABC123"}');
  assert.match(calls[0].options.headers['X-Correlation-Id'], uuid);
  assert.notEqual(calls[0].options.headers['X-Correlation-Id'], calls[1].options.headers['X-Correlation-Id']);
});

test('un DELETE 204 termina correctamente sin intentar interpretar JSON', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response(null, { status: 204 }));
  assert.equal(await request('/api/v1', '/vehiculos/8', { method: 'DELETE' }), undefined);
  assert.equal(fetch.mock.callCount(), 1);
});

test('conserva mensaje, correlación y detalles válidos del ErrorResponse 400', async t => {
  const correlationId = 'ed894bcb-ef13-40bc-bdf0-d99fb27f263e';
  t.mock.method(globalThis, 'fetch', async () => Response.json({
    status: 400, message: 'La capacidad no es válida.', correlationId,
    detalles: [{ campo: 'capacidad', problema: 'Debe ser positiva.' }, { campo: 'secreto' }, null],
  }, { status: 400 }));
  await assert.rejects(request('/api/v1', '/vehiculos', { method: 'POST', body: {} }), error => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 400);
    assert.equal(error.message, 'La capacidad no es válida.');
    assert.equal(error.correlationId, correlationId);
    assert.deepEqual(error.detalles, [{ campo: 'capacidad', problema: 'Debe ser positiva.' }]);
    return true;
  });
});

test('un 401 sin JSON informa que la sesión terminó', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('', { status: 401 }));
  await assert.rejects(request('/api/v1', '/auth/me'), error => error instanceof ApiError && error.status === 401 && /sesión terminó/.test(error.message));
});

test('un 503 HTML entrega un error seguro y la correlación de cabecera', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => new Response('<html>error interno de proxy</html>', {
    status: 503, headers: { 'X-Correlation-Id': 'ed894bcb-ef13-40bc-bdf0-d99fb27f263e' },
  }));
  await assert.rejects(request('/api/v1', '/viajes'), error => {
    assert.equal(error.status, 503);
    assert.equal(error.correlationId, 'ed894bcb-ef13-40bc-bdf0-d99fb27f263e');
    assert.match(error.message, /servicio no está disponible/);
    assert.doesNotMatch(error.message, /<html>|interno de proxy/);
    return true;
  });
  assert.equal(fetch.mock.callCount(), 1);
});

test('no reintenta una mutación cuando la red falla', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('network failure'); });
  await assert.rejects(request('/api/v1', '/viajes', { method: 'POST', body: {} }), error => error instanceof ApiError && error.status === 0 && /conectar/.test(error.message));
  assert.equal(fetch.mock.callCount(), 1);
});

test('aborta una mutación por tiempo sin reenviarla', async t => {
  const fetch = t.mock.method(globalThis, 'fetch', async (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  }));
  await assert.rejects(request('/api/v1', '/viajes', { method: 'POST', body: {}, timeoutMs: 10 }), error => {
    assert.equal(error.status, 0);
    assert.match(error.message, /tardó demasiado/);
    assert.match(error.message, /consulta los datos antes/);
    return true;
  });
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(fetch.mock.calls[0].arguments[1].signal.aborted, true);
});

test('un éxito con HTML se rechaza como respuesta inesperada', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('<html>servidor equivocado</html>'));
  await assert.rejects(request('/api/v1', '/viajes'), error => error instanceof ApiError && error.status === 200 && /respuesta inesperada/.test(error.message));
});

test('query omite valores vacíos, conserva cero y codifica caracteres', () => {
  const result = query({ estado: 'ACTIVO', desde: '', hasta: undefined, filtro: null, pagina: 0, texto: 'Bogotá & campus' });
  const params = new URLSearchParams(result.slice(1));
  assert.equal(params.get('estado'), 'ACTIVO');
  assert.equal(params.get('pagina'), '0');
  assert.equal(params.get('texto'), 'Bogotá & campus');
  assert.equal(params.has('desde'), false);
  assert.equal(params.has('hasta'), false);
  assert.equal(params.has('filtro'), false);
  assert.equal(query({ omitido: undefined }), '');
});
