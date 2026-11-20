const config = require('../config/env');
const { AppError } = require('../utils/errores');

const esId = (v) => Number.isInteger(v) && v > 0 && v <= 2147483647;

function esVehiculoValido(v, vehiculoId) {
  return (
    v !== null &&
    typeof v === 'object' &&
    !Array.isArray(v) &&
    esId(v.vehiculoId) && v.vehiculoId === vehiculoId &&
    esId(v.conductorId) &&
    esId(v.capacidad) &&
    ['ACTIVO', 'INACTIVO'].includes(v.estado)
  );
}

/**
 * GET /api/v1/vehiculos/{vehiculoId} reenviando el JWT del conductor.
 * - 200: devuelve el vehículo
 * - 401/403/404: se propagan con su propio error
 * - Caída, timeout o respuesta inválida: 1 reintento y luego 503
 */
async function obtenerVehiculo(vehiculoId, { token, correlationId, conductorId }) {
  const url = `${config.vehiculosUrl}/api/v1/vehiculos/${vehiculoId}`;
  const headers = {
    Authorization: `Bearer ${token}`,
    'X-Correlation-Id': correlationId,
    Accept: 'application/json',
  };

  for (let intento = 0; intento <= config.httpMaxRetries; intento++) {
    try {
      const resp = await fetch(url, {
        method: 'GET',
        headers,
        signal: AbortSignal.timeout(config.httpTimeoutMs),
      });

      if (resp.status === 200) {
        const cuerpo = await resp.json();
        if (!esVehiculoValido(cuerpo, vehiculoId)) {
          throw new Error('Respuesta inválida del servicio de Vehículos');
        }
        if (cuerpo.conductorId !== conductorId) {
          throw new AppError(403, 'NO_AUTORIZADO', 'El vehículo pertenece a otro conductor.');
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
    }
  }

  console.error(
    JSON.stringify({
      nivel: 'ERROR',
      dependencia: 'ms-vehiculos',
      correlationId,
      detalle: 'No se obtuvo una respuesta válida de Vehículos.',
    })
  );
  throw new AppError(
    503,
    'SERVICIO_DEPENDIENTE_NO_DISPONIBLE',
    'El servicio de Vehículos no está disponible. Intenta de nuevo más tarde.'
  );
}

module.exports = { obtenerVehiculo };
