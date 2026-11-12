const { randomUUID } = require('crypto');

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Si llega un X-Correlation-Id válido (UUID) lo conserva; si no, genera uno.
// Lo reenvía a los servicios y lo devuelve en la respuesta.
module.exports = (req, res, next) => {
  const entrante = (req.get('X-Correlation-Id') || '').trim();
  req.correlationId = UUID.test(entrante) ? entrante : randomUUID();
  req.headers['x-correlation-id'] = req.correlationId; // esto es lo que viaja al servicio
  req.inicioMs = Date.now();
  res.set('X-Correlation-Id', req.correlationId);
  next();
};