const path = require('node:path');
require('dotenv').config({ path: path.resolve(__dirname, '../../.env') });

function entero(nombre, defecto, minimo, maximo) {
  const texto = process.env[nombre] ?? String(defecto);
  const valor = /^\d+$/.test(texto) ? Number(texto) : NaN;
  if (!Number.isSafeInteger(valor) || valor < minimo || valor > maximo) {
    throw new Error(`Configuración inválida: ${nombre}.`);
  }
  return valor;
}

function origen(nombre, valor) {
  try {
    const url = new URL(valor);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.pathname !== '/' || url.search || url.hash) throw new Error();
    return url.origin;
  } catch { throw new Error(`Configuración inválida: ${nombre}; usa un origen HTTP sin rutas ni credenciales.`); }
}

function requerido(nombre) {
  const valor = process.env[nombre]?.trim();
  if (!valor) throw new Error(`Falta configurar ${nombre}.`);
  return valor;
}

module.exports = {
  host: process.env.SERVER_HOST?.trim() || '0.0.0.0',
  port: entero('SERVER_PORT', 8080, 1, 65535),
  usuariosUrl: origen('USUARIOS_SERVICE_URL', requerido('USUARIOS_SERVICE_URL')),
  vehiculosUrl: origen('VEHICULOS_SERVICE_URL', requerido('VEHICULOS_SERVICE_URL')),
  viajesUrl: origen('VIAJES_SERVICE_URL', requerido('VIAJES_SERVICE_URL')),
  reservasUrl: origen('RESERVAS_SERVICE_URL', requerido('RESERVAS_SERVICE_URL')),
  gatewayTimeoutMs: entero('GATEWAY_TIMEOUT_MS', 20000, 1, 120000),
  readinessTimeoutMs: entero('READINESS_TIMEOUT_MS', 8000, 1, 30000),
  frontendOrigins: requerido('FRONTEND_ORIGIN').split(',')
    .map(valor => origen('FRONTEND_ORIGIN', valor.trim())),
};
