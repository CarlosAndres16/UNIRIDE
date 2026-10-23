const service = require('../services/viajeService');
const { aViajeResponse, aOcupacionResponse } = require('../mappers/viajeMapper');
const {
  validarCrearViaje,
  validarActualizarViaje,
  validarOcupacion,
  validarFiltros,
  leerIdRuta,
  leerIfMatch,
  leerIdempotencyKey,
} = require('../utils/validaciones');

const contexto = (req) => ({
  conductorId: req.conductorId,
  token: req.token,
  correlationId: req.correlationId,
});

async function crear(req, res) {
  const datos = validarCrearViaje(req.body);
  const idempotencyKey = leerIdempotencyKey(req);
  const viaje = await service.crear(contexto(req), datos, idempotencyKey);
  res.status(201).location(`/api/v1/viajes/${viaje.id}`).json(aViajeResponse(viaje));
}

async function consultar(req, res) {
  const viajeId = leerIdRuta(req.params.viajeId, 'viajeId');
  const viaje = await service.consultar(viajeId);
  res.status(200).json(aViajeResponse(viaje));
}

async function buscar(req, res) {
  const filtros = validarFiltros(req.query);
  const { filas, paginacion } = await service.buscar(filtros);
  res.status(200).json({ datos: filas.map(aViajeResponse), paginacion });
}

async function modificar(req, res) {
  const viajeId = leerIdRuta(req.params.viajeId, 'viajeId');
  const versionEsperada = leerIfMatch(req);
  const datos = validarActualizarViaje(req.body);
  const viaje = await service.modificar(contexto(req), viajeId, datos, versionEsperada);
  res.status(200).json(aViajeResponse(viaje));
}

async function cancelar(req, res) {
  const viajeId = leerIdRuta(req.params.viajeId, 'viajeId');
  await service.cancelar(contexto(req), viajeId);
  res.status(204).send();
}

async function finalizar(req, res) {
  const viajeId = leerIdRuta(req.params.viajeId, 'viajeId');
  const viaje = await service.finalizar(contexto(req), viajeId);
  res.status(200).json(aViajeResponse(viaje));
}

async function ocupacion(req, res) {
  const viajeId = leerIdRuta(req.params.viajeId, 'viajeId');
  const { cuposOcupados } = validarOcupacion(req.body);
  const viaje = await service.actualizarOcupacion(viajeId, cuposOcupados);
  res.status(200).json(aOcupacionResponse(viaje));
}

module.exports = { crear, consultar, buscar, modificar, cancelar, finalizar, ocupacion };