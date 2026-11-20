const config = require('./config/env');
const pool = require('./config/db');
const app = require('./app');

async function iniciar() {
  try {
    await pool.query('SELECT 1');
    console.log('Conexión a la base de datos OK');
  } catch (err) {
    console.error('No se pudo conectar a la base de datos. Revisa la configuración y disponibilidad de PostgreSQL.');
    process.exit(1);
  }

  const servidor = app.listen(config.port, config.host, () => {
    console.log(`ms-viajes escuchando en http://${config.host}:${config.port}`);
  });

  const apagar = () => {
    console.log('Cerrando ms-viajes...');
    servidor.close(async () => {
      await pool.end();
      process.exit(0);
    });
  };
  process.on('SIGINT', apagar);
  process.on('SIGTERM', apagar);
}

iniciar();
