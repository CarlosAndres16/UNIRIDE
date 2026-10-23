const { createHash, timingSafeEqual } = require('crypto');
const config = require('../config/env');
const { AppError } = require('../utils/errores');

const hash = (texto) => createHash('sha256').update(texto).digest();

module.exports = (req, res, next) => {
  const recibida = req.get('X-Service-Key');
  const valida =
    typeof recibida === 'string' &&
    timingSafeEqual(hash(recibida), hash(config.serviceApiKey));

  if (!valida) {
    return next(new AppError(401, 'NO_AUTENTICADO', 'Llave de servicio ausente o inválida.'));
  }
  return next();
};