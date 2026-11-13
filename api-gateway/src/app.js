const express = require('express');
const correlationId = require('./middlewares/correlationId');
const cors = require('./middlewares/cors');
const bloquearOcupacion = require('./middlewares/bloquearOcupacion');
const { notFound, errorHandler } = require('./middlewares/errores');
const crearProxy = require('./proxy/crearProxy');
const rutas = require('./config/rutas');

const app = express();

app.disable('x-powered-by');

// IMPORTANTE: NO usar express.json() aquí. Si el Gateway consume el body,
// el servicio destino recibe la petición vacía y se cuelga.
app.use(correlationId);

app.use((req, res, next) => {
  res.on('finish', () => {
    console.log(
      `${new Date().toISOString()} ${req.method} ${req.originalUrl} ${res.statusCode} cid=${req.correlationId}`
    );
  });
  next();
});

app.use(cors);

// Propio del Gateway; no se enruta a ningún servicio.
app.get('/health', (req, res) =>
  res.json({ status: 'UP', servicio: 'api-gateway' })
);

app.use(bloquearOcupacion);

rutas.forEach((ruta) => app.use(crearProxy(ruta)));

app.use(notFound);
app.use(errorHandler);

module.exports = app;