const express = require('express');
const correlationId = require('./middlewares/correlationId');
const viajeRoutes = require('./routes/viajeRoutes');
const { notFound, errorHandler } = require('./middlewares/errorHandler');

const app = express();

app.disable('x-powered-by');
app.use(correlationId);
app.use(express.json({ limit: '100kb' }));

app.use((req, res, next) => {
  res.on('finish', () => {
    console.log(
      `${new Date().toISOString()} ${req.method} ${req.originalUrl} ${res.statusCode} cid=${req.correlationId}`
    );
  });
  next();
});

// Solo para desarrollo/monitoreo; el Gateway no lo publica
app.get('/health', (req, res) => res.json({ status: 'UP', servicio: 'ms-viajes' }));

app.use('/api/v1/viajes', viajeRoutes);

app.use(notFound);
app.use(errorHandler);

module.exports = app;