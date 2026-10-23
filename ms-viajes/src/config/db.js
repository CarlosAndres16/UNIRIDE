const { Pool, types } = require('pg');
const config = require('./env');

// DATE (oid 1082) se devuelve como texto "YYYY-MM-DD" para evitar desfases de zona horaria
types.setTypeParser(1082, (valor) => valor);

const pool = new Pool({
  host: config.db.host,
  port: config.db.port,
  database: config.db.database,
  user: config.db.user,
  password: config.db.password,
  max: 10,
});

pool.on('error', (err) => {
  console.error('Error inesperado en el pool de PostgreSQL:', err.message);
});

module.exports = pool;