const env = require('./config/env');
const app = require('./app');

app.listen(env.port, '0.0.0.0', () => {
  console.log(`api-gateway escuchando en el puerto ${env.port} (todas las interfaces)`);
});