require('dotenv').config();

const requeridas = [
  'SERVER_PORT',
  'USUARIOS_SERVICE_URL',
  'VEHICULOS_SERVICE_URL',
  'VIAJES_SERVICE_URL',
  'RESERVAS_SERVICE_URL',
  'GATEWAY_TIMEOUT_MS',
  'FRONTEND_ORIGIN',
];

const faltantes = requeridas.filter(
  (nombre) => !process.env[nombre] || process.env[nombre].trim() === ''
);

if (faltantes.length > 0) {
  console.error(`Faltan variables de entorno: ${faltantes.join(', ')}`);
  process.exit(1);
}

const sinBarraFinal = (url) => url.trim().replace(/\/+$/, '');

module.exports = {
  port: Number(process.env.SERVER_PORT),
  usuariosUrl: sinBarraFinal(process.env.USUARIOS_SERVICE_URL),
  vehiculosUrl: sinBarraFinal(process.env.VEHICULOS_SERVICE_URL),
  viajesUrl: sinBarraFinal(process.env.VIAJES_SERVICE_URL),
  reservasUrl: sinBarraFinal(process.env.RESERVAS_SERVICE_URL),
  gatewayTimeoutMs: Number(process.env.GATEWAY_TIMEOUT_MS),
  frontendOrigins: process.env.FRONTEND_ORIGIN
    .split(',')
    .map(sinBarraFinal)
    .filter(Boolean),
};