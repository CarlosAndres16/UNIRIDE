const env = require('./config/env');
const app = require('./app');

const server = app.listen(env.port, env.host, () => {
  console.log(`api-gateway escuchando en ${env.host}:${env.port}`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
