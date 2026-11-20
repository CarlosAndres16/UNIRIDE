const jwt = require('jsonwebtoken');
const config = require('../config/env');
const { AppError } = require('../utils/errores');

const noAutenticado = () =>
  new AppError(401, 'NO_AUTENTICADO', 'Token ausente, inválido o vencido.');

module.exports = (req, res, next) => {
  const cabecera = req.get('Authorization') || '';
  const partes = /^Bearer\s+(\S+)$/i.exec(cabecera);
  const token = partes?.[1];

  if (!token) return next(noAutenticado());

  try {
    const payload = jwt.verify(token, config.jwtSecret, { algorithms: ['HS256'] });
    const conductorId = Number(payload.sub);
    if (typeof payload.sub !== 'string' || !/^\d+$/.test(payload.sub) ||
        !Number.isInteger(conductorId) || conductorId <= 0 || conductorId > 2147483647 ||
        !Number.isSafeInteger(payload.iat) || payload.iat < 0 ||
        !Number.isSafeInteger(payload.exp) || payload.exp < payload.iat) {
      return next(noAutenticado());
    }
    req.conductorId = conductorId; // sale de sub, nunca del body
    req.token = token; // se reenvía a Vehículos
    return next();
  } catch (err) {
    return next(noAutenticado());
  }
};
