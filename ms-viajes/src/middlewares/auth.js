const jwt = require('jsonwebtoken');
const config = require('../config/env');
const { AppError } = require('../utils/errores');

const noAutenticado = () =>
  new AppError(401, 'NO_AUTENTICADO', 'Token ausente, inválido o vencido.');

module.exports = (req, res, next) => {
  const cabecera = req.get('Authorization') || '';
  const [esquema, token] = cabecera.split(' ');

  if (esquema !== 'Bearer' || !token) return next(noAutenticado());

  try {
    const payload = jwt.verify(token, config.jwtSecret, { algorithms: ['HS256'] });
    const conductorId = Number(payload.sub);
    if (!Number.isInteger(conductorId) || conductorId <= 0) {
      return next(noAutenticado());
    }
    req.conductorId = conductorId; // sale de sub, nunca del body
    req.token = token; // se reenvía a Vehículos
    return next();
  } catch (err) {
    return next(noAutenticado());
  }
};