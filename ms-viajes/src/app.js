const express = require('express');
const correlationId = require('./middlewares/correlationId');
const viajeRoutes = require('./routes/viajeRoutes');
const { notFound, errorHandler } = require('./middlewares/errorHandler');
const pool = require('./config/db');

const app = express();

app.disable('x-powered-by');
app.use(correlationId);
app.use(express.json({ limit: '100kb' }));

app.use((req, res, next) => {
  res.on('finish', () => {
    console.log(
      `${new Date().toISOString()} ${req.method} ${req.originalUrl.split('?')[0]} ${res.statusCode} cid=${req.correlationId}`
    );
  });
  next();
});

// Solo para desarrollo/monitoreo; el Gateway no lo publica
app.get('/health', (req, res) => res.json({ status: 'UP', servicio: 'ms-viajes' }));
app.get('/health/ready', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'UP', servicio: 'ms-viajes', database: 'UP' });
  } catch {
    res.status(503).json({ status: 'DOWN', servicio: 'ms-viajes', database: 'DOWN' });
  }
});

app.use('/api/v1/viajes', viajeRoutes);

app.use(notFound);
app.use(errorHandler);

module.exports = app;
