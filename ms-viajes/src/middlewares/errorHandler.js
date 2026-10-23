const { AppError } = require('../utils/errores');
const { aIsoUtc } = require('../utils/fechas');

const rutaSinQuery = (req) => req.originalUrl.split('?')[0];

function notFound(req, res, next) {
  next(new AppError(404, 'RUTA_NO_ENCONTRADA', `No existe la ruta ${req.method} ${rutaSinQuery(req)}.`));
}

// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  if (res.headersSent) return next(err);

  let status = 500;
  let error = 'ERROR_INTERNO';
  let message = 'Ocurrió un error interno. Intenta de nuevo más tarde.';
  let detalles;

  if (err instanceof AppError) {
    status = err.status;
    error = err.error;
    message = err.message;
    detalles = err.detalles;
  } else if (err.type === 'entity.parse.failed') {
    status = 400;
    error = 'SOLICITUD_INVALIDA';
    message = 'El cuerpo de la solicitud no es un JSON válido.';
  } else if (err.type === 'entity.too.large') {
    status = 400;
    error = 'SOLICITUD_INVALIDA';
    message = 'El cuerpo de la solicitud es demasiado grande.';
  }

  if (status >= 500) {
    console.error(
      JSON.stringify({
        nivel: 'ERROR',
        timestamp: aIsoUtc(new Date()),
        correlationId: req.correlationId,
        ruta: `${req.method} ${rutaSinQuery(req)}`,
        error,
        detalle: err.message,
        stack: err.stack,
      })
    );
  }

  const cuerpo = {
    timestamp: aIsoUtc(new Date()),
    status,
    error,
    message,
    path: rutaSinQuery(req),
    correlationId: req.correlationId,
  };
  if (detalles) cuerpo.detalles = detalles;

  return res.status(status).json(cuerpo);
}

module.exports = { notFound, errorHandler };