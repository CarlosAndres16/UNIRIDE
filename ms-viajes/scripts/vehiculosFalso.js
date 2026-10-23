require('dotenv').config();
const http = require('http');
const jwt = require('jsonwebtoken');

http
  .createServer((req, res) => {
    const enviar = (status, cuerpo) => {
      res.writeHead(status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(cuerpo));
    };

    const token = (req.headers.authorization || '').replace('Bearer ', '');
    let conductorId;
    try {
      conductorId = Number(
        jwt.verify(token, process.env.JWT_SECRET, { algorithms: ['HS256'] }).sub
      );
    } catch (e) {
      return enviar(401, { error: 'NO_AUTENTICADO' });
    }

    const m = req.url.match(/^\/api\/v1\/vehiculos\/(\d+)$/);
    if (!m) return enviar(404, { error: 'RUTA_NO_ENCONTRADA' });

    const id = Number(m[1]);
    if (id === 99) return enviar(404, { error: 'VEHICULO_NO_ENCONTRADO' });
    if (id === 98) return enviar(403, { error: 'NO_AUTORIZADO' });

    return enviar(200, {
      vehiculoId: id,
      conductorId,
      placa: 'ABC123',
      marca: 'Renault',
      modelo: 'Logan',
      color: 'Gris',
      tipo: 'Automovil',
      capacidad: 4,
      estado: id === 2 ? 'INACTIVO' : 'ACTIVO',
    });
  })
  .listen(8082, () => console.log('Vehículos falso escuchando en http://localhost:8082'));