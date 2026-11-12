const cors = require('cors');
const env = require('../config/env');

// CORS solo en el Gateway (D-24). Los servicios no lo habilitan.
module.exports = cors({
  origin: env.frontendOrigins,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
  allowedHeaders: [
    'Authorization',
    'Content-Type',
    'X-Correlation-Id',
    'Idempotency-Key',
    'If-Match',
  ],
  exposedHeaders: ['X-Correlation-Id', 'Location', 'ETag'],
  maxAge: 600,
});