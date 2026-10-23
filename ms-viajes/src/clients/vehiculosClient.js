const config = require('../config/env');
const { AppError } = require('../utils/errores');

function esVehiculoValido(v) {
  return (
    v !== null &&
    typeof v === 'object' &&
    Number.isInteger(v.vehiculoId) &&
    Number.isInteger(v.conductorId) &&
    typeof v.estado === 'string'
  );
}

/**
 * GET /api/v1/vehiculos/{vehiculoId} reenviando el JWT del conductor.
 * - 200: devuelve el vehículo
 * - 401/403/404: se propagan con su propio error
 * - Caída, timeout o respuesta inválida: 1 reintento y luego 503
 */
async function obtenerVehiculo(vehiculoId, { token, correlationId }) {
  const url = `${config.vehiculosUrl}/api/v1/vehiculos/${vehiculoId}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    'X-Correlation-Id': correlationId,
    Accept: 'application/json',
  };

  let ultimoError = null;

  for (let intento = 0; intento <= config.httpMaxRetries; intento++) {
    try {
      const resp = await fetch(url, {
        method: 'GET',
        headers,
        signal: AbortSignal.timeout(config.httpTimeoutMs),
      });

      if (resp.status === 200) {
        const cuerpo = await resp.json();
        if (!esVehiculoValido(cuerpo)) {
          throw new Error('Respuesta inválida del servicio de Vehículos');
        }
        return cuerpo;
      }
      if (resp.status === 401) {
        throw new AppError(401, 'NO_AUTENTICADO', 'Token ausente, inválido o vencido.');
      }
      if (resp.status === 403) {
        throw new AppError(403, 'NO_AUTORIZADO', 'El vehículo pertenece a otro conductor.');
      }
      if (resp.status === 404) {
        throw new AppError(404, 'VEHICULO_NO_ENCONTRADO', `No existe un vehículo con id ${vehiculoId}.`);
      }
      throw new Error(`Vehículos respondió con estado ${resp.status}`);
    } catch (err) {
      if (err instanceof AppError) throw err; // errores del proveedor: no se reintentan
      ultimoError = err;
    }
  }

  console.error(
    JSON.stringify({
      nivel: 'ERROR',
      dependencia: 'ms-vehiculos',
      correlationId,
      detalle: ultimoError ? ultimoError.message : 'desconocido',
    })
  );
  throw new AppError(
    503,
    'SERVICIO_DEPENDIENTE_NO_DISPONIBLE',
    'El servicio de Vehículos no está disponible. Intenta de nuevo más tarde.'
  );
}

module.exports = { obtenerVehiculo };