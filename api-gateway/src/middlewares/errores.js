const { enviarError } = require('../utils/respuestaError');

function notFound(req, res) {
  enviarError(
    req,
    res,
    404,
    'RUTA_NO_ENCONTRADA',
    `No existe la ruta ${req.method} ${req.originalUrl.split('?')[0]}.`
  );
}

// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  if (res.headersSent) return next(err);
  console.error(
    JSON.stringify({
      nivel: 'ERROR',
      timestamp: new Date().toISOString(),
      correlationId: req.correlationId,
      ruta: `${req.method} ${req.originalUrl.split('?')[0]}`,
      detalle: err.message,
    })
  );
  enviarError(
    req,
    res,
    500,
    'ERROR_INTERNO',
    'Ocurrió un error interno. Intenta de nuevo más tarde.'
  );
}

module.exports = { notFound, errorHandler };