const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const base = {
  ...process.env, SERVER_HOST: '', SERVER_PORT: '8083', DB_HOST: '127.0.0.1', DB_PORT: '5432',
  DB_NAME: 'test', DB_USER: 'test', DB_PASSWORD: 'test-only', JWT_SECRET: 'test-only-secret',
  SERVICE_API_KEY: 'test-only-key', VEHICULOS_SERVICE_URL: 'http://25.0.88.33:8082/',
  HTTP_TIMEOUT_MS: '3000', HTTP_MAX_RETRIES: '1',
};
const ruta = path.resolve(__dirname, '../src/config/env.js');
const cargar = (cambios = {}) => spawnSync(process.execPath,
  ['-e', `const c = require(${JSON.stringify(ruta)}); console.log(JSON.stringify({host:c.host,port:c.port,url:c.vehiculosUrl}));`],
  { cwd: __dirname, env: { ...base, ...cambios }, encoding: 'utf8' });

test('config acepta URL Hamachi, normaliza slash y escucha en 0.0.0.0 por defecto', () => {
  const r = cargar();
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(JSON.parse(r.stdout), { host: '0.0.0.0', port: 8083, url: 'http://25.0.88.33:8082' });
  assert.equal(JSON.parse(cargar({ SERVER_HOST: '127.0.0.1' }).stdout).host, '127.0.0.1');
});

test('config rechaza puertos/timeouts/reintentos inválidos antes de iniciar', () => {
  for (const [nombre, valores] of Object.entries({
    SERVER_PORT: ['0', '65536', 'abc'], DB_PORT: ['1.5', '65536'],
    HTTP_TIMEOUT_MS: ['0', '-1', 'NaN', '120001'], HTTP_MAX_RETRIES: ['-1', '1.5', '4'],
  })) {
    for (const valor of valores) {
      const r = cargar({ [nombre]: valor });
      assert.notEqual(r.status, 0);
      assert.match(r.stderr, new RegExp(nombre));
    }
  }
});

test('config rechaza URLs inseguras o inválidas sin imprimir sus valores', () => {
  for (const valor of ['postgres://secret-no-mostrar@host/db', 'http://usuario:secret-no-mostrar@host',
    'secret-no-mostrar', 'http://host?secret-no-mostrar', 'http://host#secret-no-mostrar']) {
    const r = cargar({ VEHICULOS_SERVICE_URL: valor });
    assert.notEqual(r.status, 0);
    assert.match(r.stderr, /VEHICULOS_SERVICE_URL/);
    assert.doesNotMatch(r.stderr + r.stdout, /secret-no-mostrar/);
  }
});

test('arranque normal carga .env.practica antes que un .env antiguo sin alterar DB', () => {
  const fs = require('node:fs');
  const setup = path.resolve(__dirname, '../.setup');
  fs.mkdirSync(setup, {recursive:true});
  const fixture = fs.mkdtempSync(path.join(setup, 'env-automatico-'));
  const config = path.join(fixture,'src','config','env.js');
  fs.mkdirSync(path.dirname(config), {recursive:true});
  fs.copyFileSync(ruta,config);
  const nuevoJwt = 'jwt-publico-ficticio-de-pruebas-1234567890';
  const nuevoService = 'llave-publica-ficticia-de-pruebas-1234567890';
  fs.writeFileSync(path.join(fixture,'.env.practica'),`JWT_SECRET=${nuevoJwt}\nSERVICE_API_KEY=${nuevoService}\n`);
  fs.writeFileSync(path.join(fixture,'.env'),'JWT_SECRET=antiguo\nSERVICE_API_KEY=antigua\n');
  const ambiente = {...base};
  delete ambiente.JWT_SECRET; delete ambiente.SERVICE_API_KEY; delete ambiente.UNIRIDE_PRACTICA_AUTO;
  const child = spawnSync(process.execPath, ['-e', `const c=require(${JSON.stringify(config)}); console.log(JSON.stringify({jwtCorrecto:c.jwtSecret===${JSON.stringify(nuevoJwt)},llaveCorrecta:c.serviceApiKey===${JSON.stringify(nuevoService)},passwordConservado:c.db.password==='test-only'}));`],
    {cwd:__dirname,env:ambiente,encoding:'utf8'});
  assert.equal(child.status,0,child.stderr);
  assert.deepEqual(JSON.parse(child.stdout),{jwtCorrecto:true,llaveCorrecta:true,passwordConservado:true});
});
