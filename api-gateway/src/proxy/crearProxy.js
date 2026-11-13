const { createProxyMiddleware } = require('http-proxy-middleware');
const env = require('../config/env');
const { enviarError } = require('../utils/respuestaError');

// Coincide con el prefijo exacto o con cualquier subruta (/api/v1/viajes, /api/v1/viajes/5, ...)
function coincidePrefijo(prefijos) {
  return (pathname) =>
    prefijos.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function crearProxy({ nombre, target, prefijos }) {
  return createProxyMiddleware({
    target,
    pathFilter: coincidePrefijo(prefijos),
    changeOrigin: true,
    xfwd: true,
    proxyTimeout: env.gatewayTimeoutMs,
    on: {
      error: (err, req, res) => {
        if (res.headersSent) {
          res.end();
          return;
        }

        const transcurrido = Date.now() - req.inicioMs;
        const esTimeout = transcurrido >= env.gatewayTimeoutMs - 200;

        console.error(
          JSON.stringify({
            nivel: 'ERROR',
            timestamp: new Date().toISOString(),
            correlationId: req.correlationId,
            dependencia: nombre,
            codigo: err.code,
            transcurridoMs: transcurrido,
            ruta: `${req.method} ${req.originalUrl.split('?')[0]}`,
          })
        );

        if (esTimeout) {
          enviarError(
            req,
            res,
            504,
            'TIEMPO_DE_ESPERA_AGOTADO',
            `El servicio ${nombre} no respondió a tiempo.`
          );
        } else {
          enviarError(
            req,
            res,
            503,
            'SERVICIO_DEPENDIENTE_NO_DISPONIBLE',
            `El servicio ${nombre} no está disponible en este momento.`
          );
        }
      },
    },
  });
}

module.exports = crearProxy;