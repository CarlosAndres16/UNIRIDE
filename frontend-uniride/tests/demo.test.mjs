import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../src/lib/http.ts';
import { demoApi, demoConductor } from '../src/lib/demo.ts';

test('dataset ficticio coherente y respuestas independientes de la memoria', async () => {
  const profile = await demoApi.me();
  assert.equal(profile.conductorId, demoConductor.conductorId);
  profile.nombre = 'Modificación externa';
  assert.equal((await demoApi.me()).nombre, 'Alejandro Moreno');
  const vehicles = await demoApi.vehicles();
  assert.equal(vehicles.datos.filter(item => item.estado === 'ACTIVO').length, 2);
  const page = await demoApi.trips({ estado: 'TODOS', tamano: 50 });
  for (const trip of page.datos) {
    const stats = await demoApi.stats('viaje', trip.viajeId);
    assert.equal(stats.cuposDisponibles, trip.cuposDisponibles);
    assert.equal(stats.cuposOfrecidos, trip.capacidad);
  }
});

test('estadísticas agregadas excluyen viajes cancelados y ponderan por cupos', async () => {
  const all = (await demoApi.trips({ estado: 'TODOS', tamano: 50 })).datos;
  const included = all.filter(item => item.estado !== 'CANCELADO');
  const stats = await demoApi.stats('conductor', 25);
  assert.equal(stats.viajesConsultados, included.length);
  assert.equal(stats.cuposOfrecidosAcumulados, included.reduce((sum, item) => sum + item.capacidad, 0));
  assert.equal(stats.pasajerosConfirmados, 10);
  assert.equal(stats.porcentajeOcupacionPromedio, 55.56);
  assert.equal(stats.totalReservas, 9);
});

test('filtros y paginación respetan estado, vehículo y rango de fechas', async () => {
  const first = await demoApi.trips({ estado: 'ACTIVO', vehiculoId: 1, pagina: 1, tamano: 1 });
  assert.equal(first.datos.length, 1);
  assert.equal(first.paginacion.totalElementos, 2);
  assert.equal(first.paginacion.totalPaginas, 2);
  const second = await demoApi.trips({ estado: 'ACTIVO', vehiculoId: 1, pagina: 2, tamano: 1 });
  assert.notEqual(second.datos[0].viajeId, first.datos[0].viajeId);
  assert.ok(first.datos[0].fechaSalida <= second.datos[0].fechaSalida);
  const date = first.datos[0].fechaSalida;
  const exact = await demoApi.trips({ desde: date, hasta: date, estado: 'ACTIVO' });
  assert.ok(exact.datos.length > 0);
  assert.ok(exact.datos.every(item => item.fechaSalida === date && item.estado === 'ACTIVO'));
});

test('publicación idempotente, edición con versión y baja lógica de vehículo', async () => {
  const car = await demoApi.saveVehicle({ placa: 'tst999', marca: 'Renault', modelo: 'Logan', color: 'Azul', tipo: 'Automóvil', capacidad: 4 });
  assert.equal(car.placa, 'TST999');
  await assert.rejects(demoApi.saveVehicle({ placa: 'TST999', marca: 'Kia', modelo: 'Rio', color: 'Negro', tipo: 'Automóvil', capacidad: 3 }), error => error instanceof ApiError && error.status === 409);
  const input = { vehiculoId: car.vehiculoId, origen: { descripcion: 'Origen de prueba', latitud: 4.6, longitud: -74.1 },
    destino: { descripcion: 'Campus de prueba', latitud: 4.7, longitud: -74.0 }, fechaSalida: '2030-02-10', horaSalida: '08:00', capacidad: 3 };
  const created = await demoApi.saveTrip(input, 'demo-test-idempotencia');
  const repeated = await demoApi.saveTrip(input, 'demo-test-idempotencia');
  assert.equal(repeated.viajeId, created.viajeId);
  assert.equal((await demoApi.reservations(created.viajeId)).total, 0);
  const changed = await demoApi.saveTrip({ ...input, capacidad: 4 }, '', created);
  assert.equal(changed.version, created.version + 1);
  assert.equal(changed.cuposDisponibles, 4);
  await assert.rejects(demoApi.saveTrip(input, '', created), error => error instanceof ApiError && error.status === 412);
  const before = await demoApi.stats('conductor', 25);
  await demoApi.cancelTrip(created.viajeId);
  const after = await demoApi.stats('conductor', 25);
  assert.equal(after.viajesConsultados, before.viajesConsultados - 1);
  assert.equal(after.cuposOfrecidosAcumulados, before.cuposOfrecidosAcumulados - 4);
  await demoApi.deactivateVehicle(car.vehiculoId);
  assert.equal((await demoApi.vehicles()).datos.find(item => item.vehiculoId === car.vehiculoId).estado, 'INACTIVO');
  await assert.rejects(demoApi.saveTrip(input, 'demo-test-inactivo'), error => error instanceof ApiError && error.status === 409);
});

test('reserva pendiente no consume cupos y el perfil admite teléfono null', async () => {
  const all = await demoApi.reservations(306);
  assert.equal(all.total, 2);
  assert.equal((await demoApi.reservations(306, 'PENDIENTE')).total, 1);
  const stats = await demoApi.stats('viaje', 306);
  assert.equal(stats.pasajerosConfirmados, 1);
  assert.equal(stats.cuposDisponibles, 2);
  const saved = await demoApi.profile({ nombre: 'Alejandro Actualizado', telefono: null });
  assert.equal(saved.telefono, null);
  assert.equal((await demoApi.me()).nombre, 'Alejandro Actualizado');
});
