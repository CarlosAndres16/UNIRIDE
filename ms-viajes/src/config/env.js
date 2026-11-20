const path = require('node:path');
const dotenv = require('dotenv');
// Las claves y direcciones de práctica ganan sobre un .env antiguo; DB_* sigue local.
// Una variable explícita del proceso conserva la prioridad habitual de dotenv.
if (process.env.UNIRIDE_PRACTICA_AUTO !== '0') {
  dotenv.config({ path: path.resolve(__dirname, '../../.env.practica') });
}
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const requeridas = [
  'SERVER_PORT',
  'DB_HOST',
  'DB_PORT',
  'DB_NAME',
  'DB_USER',
  'DB_PASSWORD',
  'JWT_SECRET',
  'SERVICE_API_KEY',
  'VEHICULOS_SERVICE_URL',
  'HTTP_TIMEOUT_MS',
  'HTTP_MAX_RETRIES',
];

const faltantes = requeridas.filter(
  (nombre) => !process.env[nombre] || process.env[nombre].trim() === ''
);

if (faltantes.length > 0) {
  throw new Error(`Faltan variables de entorno: ${faltantes.join(', ')}`);
}

function entero(nombre, minimo, maximo) {
  const valor = process.env[nombre].trim();
  if (!/^\d+$/.test(valor) || !Number.isSafeInteger(Number(valor)) ||
      Number(valor) < minimo || Number(valor) > maximo) {
    throw new Error(`Configuración inválida: ${nombre} debe ser un entero entre ${minimo} y ${maximo}.`);
  }
  return Number(valor);
}

function urlServicio(nombre) {
  try {
    const url = new URL(process.env[nombre]);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.search || url.hash) throw new Error();
    return url.toString().replace(/\/+$/, '');
  } catch {
    // Nunca incluir el valor: una URL mal configurada puede contener credenciales.
    throw new Error(`Configuración inválida: ${nombre} debe ser una URL HTTP(S) sin credenciales, query ni fragmento.`);
  }
}

const host = process.env.SERVER_HOST?.trim() || '0.0.0.0';
if (!/^[a-zA-Z0-9.:-]+$/.test(host)) {
  throw new Error('Configuración inválida: SERVER_HOST debe ser una IP o nombre de host.');
}

module.exports = {
  host,
  port: entero('SERVER_PORT', 1, 65535),
  db: {
    host: process.env.DB_HOST,
    port: entero('DB_PORT', 1, 65535),
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
  },
  jwtSecret: process.env.JWT_SECRET,
  serviceApiKey: process.env.SERVICE_API_KEY,
  vehiculosUrl: urlServicio('VEHICULOS_SERVICE_URL'),
  httpTimeoutMs: entero('HTTP_TIMEOUT_MS', 1, 120000),
  httpMaxRetries: entero('HTTP_MAX_RETRIES', 0, 3),
};
