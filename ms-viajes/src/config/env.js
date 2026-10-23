require('dotenv').config();

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
  console.error(`Faltan variables de entorno: ${faltantes.join(', ')}`);
  process.exit(1);
}

module.exports = {
  port: Number(process.env.SERVER_PORT),
  db: {
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT),
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
  },
  jwtSecret: process.env.JWT_SECRET,
  serviceApiKey: process.env.SERVICE_API_KEY,
  vehiculosUrl: process.env.VEHICULOS_SERVICE_URL.replace(/\/+$/, ''),
  httpTimeoutMs: Number(process.env.HTTP_TIMEOUT_MS),
  httpMaxRetries: Number(process.env.HTTP_MAX_RETRIES),
};