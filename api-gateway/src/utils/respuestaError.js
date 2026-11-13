// Formato único de error (sección 7, D-05)
function enviarError(req, res, status, error, message) {
  res.status(status).json({
    timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    status,
    error,
    message,
    path: req.originalUrl.split('?')[0],
    correlationId: req.correlationId,
  });
}

module.exports = { enviarError };