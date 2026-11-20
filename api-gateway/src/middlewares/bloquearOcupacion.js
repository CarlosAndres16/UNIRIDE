const { enviarError } = require('../utils/respuestaError');

// PUT /api/v1/viajes/{viajeId}/ocupacion es solo entre servicios:
// el Gateway no lo publica (secciones 4 y 5 del contrato).
const RUTA_OCUPACION = /^\/api\/v1\/viajes\/[^/]+\/ocupacion\/?$/i;

module.exports = (req, res, next) => {
  let ruta;
  try { ruta = decodeURIComponent(req.path); } catch { ruta = req.path; }
  if (RUTA_OCUPACION.test(ruta)) {
    return enviarError(
      req,
      res,
      404,
      'RUTA_NO_ENCONTRADA',
      `No existe la ruta ${req.method} ${req.path}.`
    );
  }
  next();
};
