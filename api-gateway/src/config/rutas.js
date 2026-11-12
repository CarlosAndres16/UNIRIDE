const env = require('./env');

// Tabla de la sección 5 del contrato: prefijo público -> servicio destino.
// La ruta interna es igual a la pública (no se reescribe nada).
module.exports = [
  {
    nombre: 'ms-usuarios-auth',
    target: env.usuariosUrl,
    prefijos: ['/api/v1/auth', '/api/v1/conductores'],
  },
  {
    nombre: 'ms-vehiculos',
    target: env.vehiculosUrl,
    prefijos: ['/api/v1/vehiculos'],
  },
  {
    nombre: 'ms-viajes',
    target: env.viajesUrl,
    prefijos: ['/api/v1/viajes'],
  },
  {
    nombre: 'ms-reservas-estadisticas',
    target: env.reservasUrl,
    prefijos: ['/api/v1/reservas', '/api/v1/estadisticas'],
  },
];