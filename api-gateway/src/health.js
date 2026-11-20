const env = require('./config/env');

async function readiness(req, res) {
  const targets = { usuarios: env.usuariosUrl, vehiculos: env.vehiculosUrl,
    viajes: env.viajesUrl, reservas: env.reservasUrl };
  const servicios = Object.fromEntries(await Promise.all(Object.entries(targets).map(async ([nombre, url]) => {
    try {
      const response = await fetch(`${url}/health/ready`, {
        signal: AbortSignal.timeout(env.readinessTimeoutMs),
        headers: { 'X-Correlation-Id': req.correlationId },
      });
      const payload = await response.json();
      return [nombre, response.ok && payload.status === 'UP' ? 'UP' : 'DOWN'];
    } catch { return [nombre, 'DOWN']; }
  })));
  const ready = Object.values(servicios).every(status => status === 'UP');
  res.status(ready ? 200 : 503).json({
    status: ready ? 'UP' : 'DOWN', servicio: 'api-gateway', servicios,
  });
}

module.exports = { readiness };
