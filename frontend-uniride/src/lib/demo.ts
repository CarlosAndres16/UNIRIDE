import type { Api, Filtros } from './api';
import { ApiError } from './http.ts';
import type { Conductor, Estadistica, Punto, Reserva, Vehiculo, VehiculoInput, Viaje, ViajeInput } from '../types';

/** Entorno de demostración aislado: datos ficticios, únicamente en memoria. */
export const demoConductor: Conductor = {
  conductorId: 25, nombre: 'Alejandro Moreno', correo: 'alejandro@ejemplo.edu.co',
  telefono: '300 123 4567', activo: true,
};
let conductor = structuredClone(demoConductor);
const vehicles: Vehiculo[] = [
  { vehiculoId: 1, conductorId: 25, placa: 'KLM482', marca: 'Renault', modelo: 'Sandero', color: 'Gris', tipo: 'Automóvil', capacidad: 4, estado: 'ACTIVO' },
  { vehiculoId: 2, conductorId: 25, placa: 'JTR718', marca: 'Chevrolet', modelo: 'Spark', color: 'Azul', tipo: 'Automóvil', capacidad: 3, estado: 'ACTIVO' },
  { vehiculoId: 3, conductorId: 25, placa: 'HBC205', marca: 'Kia', modelo: 'Picanto', color: 'Blanco', tipo: 'Automóvil', capacidad: 3, estado: 'INACTIVO' },
];
function day(offset: number): string {
  const date = new Date(); date.setDate(date.getDate() + offset);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
const campus: Punto = { descripcion: 'Campus universitario', latitud: 4.6284, longitud: -74.0644 };
const norte: Punto = { descripcion: 'Portal del Norte', latitud: 4.7544, longitud: -74.0450 };
const centro: Punto = { descripcion: 'Centro · Parque de los Periodistas', latitud: 4.6017, longitud: -74.0706 };
const occidente: Punto = { descripcion: 'Centro comercial Gran Estación', latitud: 4.6477, longitud: -74.1013 };
const trips: Viaje[] = [
  { viajeId: 305, conductorId: 25, vehiculoId: 1, origen: norte, destino: campus, fechaSalida: day(1), horaSalida: '07:00:00', capacidad: 4, cuposDisponibles: 1, estado: 'ACTIVO', version: 1 },
  { viajeId: 306, conductorId: 25, vehiculoId: 2, origen: campus, destino: centro, fechaSalida: day(1), horaSalida: '17:30:00', capacidad: 3, cuposDisponibles: 2, estado: 'ACTIVO', version: 1 },
  { viajeId: 307, conductorId: 25, vehiculoId: 1, origen: occidente, destino: campus, fechaSalida: day(2), horaSalida: '06:45:00', capacidad: 4, cuposDisponibles: 4, estado: 'ACTIVO', version: 1 },
  { viajeId: 308, conductorId: 25, vehiculoId: 1, origen: campus, destino: norte, fechaSalida: day(-1), horaSalida: '18:00:00', capacidad: 4, cuposDisponibles: 0, estado: 'FINALIZADO', version: 2 },
  { viajeId: 309, conductorId: 25, vehiculoId: 2, origen: centro, destino: campus, fechaSalida: day(-2), horaSalida: '07:15:00', capacidad: 3, cuposDisponibles: 1, estado: 'FINALIZADO', version: 2 },
  { viajeId: 310, conductorId: 25, vehiculoId: 1, origen: norte, destino: campus, fechaSalida: day(-3), horaSalida: '07:00:00', capacidad: 4, cuposDisponibles: 4, estado: 'CANCELADO', version: 2 },
];
const reservations: Reserva[] = [
  { reservaId: 21, viajeId: 305, pasajeroNombre: 'Laura Gómez', cuposReservados: 1, estado: 'CONFIRMADA', fechaReserva: `${day(0)}T09:10:00Z` },
  { reservaId: 22, viajeId: 305, pasajeroNombre: 'David Rodríguez', cuposReservados: 2, estado: 'CONFIRMADA', fechaReserva: `${day(0)}T09:35:00Z` },
  { reservaId: 23, viajeId: 305, pasajeroNombre: 'Carlos Pérez', cuposReservados: 1, estado: 'CANCELADA', fechaReserva: `${day(0)}T10:00:00Z` },
  { reservaId: 24, viajeId: 306, pasajeroNombre: 'Valentina Rojas', cuposReservados: 1, estado: 'CONFIRMADA', fechaReserva: `${day(0)}T10:20:00Z` },
  { reservaId: 25, viajeId: 306, pasajeroNombre: 'Daniel Torres', cuposReservados: 1, estado: 'PENDIENTE', fechaReserva: `${day(0)}T10:45:00Z` },
  { reservaId: 26, viajeId: 308, pasajeroNombre: 'Camila Díaz', cuposReservados: 2, estado: 'CONFIRMADA', fechaReserva: `${day(-2)}T15:20:00Z` },
  { reservaId: 27, viajeId: 308, pasajeroNombre: 'Andrés López', cuposReservados: 2, estado: 'CONFIRMADA', fechaReserva: `${day(-2)}T16:00:00Z` },
  { reservaId: 28, viajeId: 309, pasajeroNombre: 'Sofía Martínez', cuposReservados: 2, estado: 'CONFIRMADA', fechaReserva: `${day(-3)}T11:30:00Z` },
  { reservaId: 29, viajeId: 309, pasajeroNombre: 'Mateo Ruiz', cuposReservados: 1, estado: 'CANCELADA', fechaReserva: `${day(-3)}T13:30:00Z` },
];
const idempotency = new Map<string, number>();
const copy = <T>(value: T): T => structuredClone(value);
const pause = () => new Promise<void>(resolve => setTimeout(resolve, 90));
const fail = (message: string, status = 400): never => { throw new ApiError(message, status); };
function vehicle(id: number): Vehiculo {
  return vehicles.find(item => item.vehiculoId === id) ?? fail('No se encontró el vehículo.', 404);
}
function trip(id: number): Viaje {
  return trips.find(item => item.viajeId === id) ?? fail('No se encontró el viaje.', 404);
}
function text(value: string, name: string, max: number): string {
  const result = typeof value === 'string' ? value.trim() : '';
  if (!result || result.length > max) fail(`${name} debe contener entre 1 y ${max} caracteres.`);
  return result;
}
function integer(value: number, name: string, min = 1): number {
  if (!Number.isInteger(value) || value < min || value > 2_147_483_647) fail(`${name} debe ser un entero válido mayor o igual a ${min}.`);
  return value;
}
function vehicleInput(body: VehiculoInput, id?: number): VehiculoInput {
  const placa = text(body.placa, 'La placa', 10).toUpperCase();
  if (vehicles.some(item => item.placa === placa && item.vehiculoId !== id)) fail('Ya existe un vehículo registrado con esa placa.', 409);
  return { placa, marca: text(body.marca, 'La marca', 50), modelo: text(body.modelo, 'El modelo', 50),
    color: text(body.color, 'El color', 30), tipo: text(body.tipo, 'El tipo', 30), capacidad: integer(body.capacidad, 'La capacidad') };
}
function point(input: Punto): Punto {
  if (!input || !Number.isFinite(input.latitud) || !Number.isFinite(input.longitud) || Math.abs(input.latitud) > 90 || Math.abs(input.longitud) > 180) fail('Las coordenadas del recorrido no son válidas.');
  return { descripcion: text(input.descripcion, 'La descripción', 200), latitud: input.latitud, longitud: input.longitud };
}
function tripInput(body: ViajeInput): ViajeInput {
  const car = vehicle(integer(body.vehiculoId, 'El vehículo'));
  if (car.estado !== 'ACTIVO') fail('Selecciona un vehículo activo.', 409);
  const capacidad = integer(body.capacidad, 'La capacidad');
  if (capacidad > 8) fail('Los cupos ofrecidos no pueden superar 8.');
  if (capacidad > car.capacidad) fail('Los cupos ofrecidos no pueden superar la capacidad del vehículo.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(body.fechaSalida) || Number.isNaN(Date.parse(`${body.fechaSalida}T12:00:00`))) fail('La fecha de salida no es válida.');
  if (!/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/.test(body.horaSalida)) fail('La hora de salida no es válida.');
  return { vehiculoId: car.vehiculoId, origen: point(body.origen), destino: point(body.destino), fechaSalida: body.fechaSalida,
    horaSalida: body.horaSalida.length === 5 ? `${body.horaSalida}:00` : body.horaSalida, capacidad };
}
function confirmed(id: number): number {
  return reservations.filter(item => item.viajeId === id && item.estado === 'CONFIRMADA').reduce((total, item) => total + item.cuposReservados, 0);
}
function filtered(filters: Filtros = {}): Viaje[] {
  const fecha = filters.fecha ?? filters.fechaSalida;
  return trips.filter(item =>
    (!filters.estado || filters.estado === 'TODOS' || item.estado === filters.estado) &&
    (!filters.vehiculoId || item.vehiculoId === Number(filters.vehiculoId)) &&
    (!filters.conductorId || item.conductorId === Number(filters.conductorId)) &&
    (!fecha || item.fechaSalida === fecha) &&
    (!filters.desde || item.fechaSalida >= String(filters.desde)) &&
    (!filters.hasta || item.fechaSalida <= String(filters.hasta)),
  ).sort((a, b) => `${a.fechaSalida}T${a.horaSalida}`.localeCompare(`${b.fechaSalida}T${b.horaSalida}`) || a.viajeId - b.viajeId);
}
function percentage(passengers: number, capacity: number): number {
  return capacity ? Math.min(100, Math.max(0, Math.round(passengers / capacity * 10000) / 100)) : 0;
}

export const demoApi: Api = {
  async me() { await pause(); return copy(conductor); },
  async profile(body) {
    await pause(); const nombre = text(body.nombre, 'El nombre', 150);
    const telefono = body.telefono === null ? null : text(body.telefono, 'El teléfono', 30);
    conductor = { ...conductor, nombre, telefono }; return copy(conductor);
  },
  async vehicles() { await pause(); return { datos: copy(vehicles) }; },
  async saveVehicle(body, id) {
    await pause(); const data = vehicleInput(body, id);
    if (id !== undefined) { const existing = vehicle(id); Object.assign(existing, data); return copy(existing); }
    const created: Vehiculo = { ...data, vehiculoId: Math.max(0, ...vehicles.map(item => item.vehiculoId)) + 1, conductorId: 25, estado: 'ACTIVO' };
    vehicles.push(created); return copy(created);
  },
  async deactivateVehicle(id) { await pause(); vehicle(id).estado = 'INACTIVO'; },
  async trips(filters = {}) {
    await pause(); const pagina = integer(Number(filters.pagina ?? 1), 'La página');
    const tamano = integer(Number(filters.tamano ?? 10), 'El tamaño de página');
    const items = filtered(filters); return { datos: copy(items.slice((pagina - 1) * tamano, pagina * tamano)),
      paginacion: { pagina, tamano, totalElementos: items.length, totalPaginas: Math.ceil(items.length / tamano) } };
  },
  async trip(id) { await pause(); return copy(trip(id)); },
  async saveTrip(body, key, existing) {
    await pause();
    if (!existing && idempotency.has(key)) return copy(trip(idempotency.get(key)!));
    const data = tripInput(body);
    if (existing) {
      const current = trip(existing.viajeId);
      if (current.version !== existing.version) fail('El viaje cambió. Actualiza sus datos antes de guardar.', 412);
      if (current.estado !== 'ACTIVO') fail('Solo puedes editar viajes activos.', 409);
      const passengers = confirmed(current.viajeId);
      if (data.capacidad < passengers) fail('Los cupos ofrecidos no pueden ser menores que los pasajeros confirmados.', 409);
      Object.assign(current, data, { cuposDisponibles: data.capacidad - passengers, version: current.version + 1, fechaActualizacion: new Date().toISOString() });
      return copy(current);
    }
    if (trips.some(item => item.estado === 'ACTIVO' && item.vehiculoId === data.vehiculoId && item.fechaSalida === data.fechaSalida && item.horaSalida === data.horaSalida)) fail('Ya existe un viaje para ese vehículo en la misma fecha y hora.', 409);
    const created: Viaje = { ...data, viajeId: Math.max(0, ...trips.map(item => item.viajeId)) + 1,
      conductorId: 25, cuposDisponibles: data.capacidad, estado: 'ACTIVO', version: 1, fechaCreacion: new Date().toISOString() };
    trips.push(created); idempotency.set(key, created.viajeId); return copy(created);
  },
  async cancelTrip(id) {
    await pause(); const current = trip(id);
    if (current.estado !== 'ACTIVO') fail('Solo puedes cancelar viajes activos.', 409);
    Object.assign(current, { estado: 'CANCELADO', version: current.version + 1, fechaActualizacion: new Date().toISOString() });
  },
  async finishTrip(id) {
    await pause(); const current = trip(id);
    if (current.estado !== 'ACTIVO') fail('Solo puedes finalizar viajes activos.', 409);
    Object.assign(current, { estado: 'FINALIZADO', version: current.version + 1, fechaActualizacion: new Date().toISOString() });
    return copy(current);
  },
  async reservations(tripId, estado) {
    await pause(); trip(tripId);
    if (estado && !['CONFIRMADA', 'PENDIENTE', 'CANCELADA'].includes(estado)) fail('El estado de reserva no es válido.');
    const datos = reservations.filter(item => item.viajeId === tripId && (!estado || item.estado === estado));
    return { viajeId: tripId, total: datos.length, datos: copy(datos) };
  },
  async stats(scope, id, filters = {}) {
    await pause();
    if (filters.desde && filters.hasta && String(filters.desde) > String(filters.hasta)) fail('La fecha inicial no puede ser posterior a la final.');
    if (scope === 'conductor' && id !== 25) fail('Solo puedes consultar tus propias estadísticas.', 403);
    if (scope === 'vehiculo') vehicle(id);
    if (scope === 'viaje') trip(id);
    const included = scope === 'viaje' ? [trip(id)] : filtered(filters).filter(item => item.estado !== 'CANCELADO' && (scope !== 'vehiculo' || item.vehiculoId === id));
    const ids = new Set(included.map(item => item.viajeId));
    const items = reservations.filter(item => ids.has(item.viajeId));
    const pasajerosConfirmados = items.filter(item => item.estado === 'CONFIRMADA').reduce((total, item) => total + item.cuposReservados, 0);
    const capacity = included.reduce((total, item) => total + item.capacidad, 0);
    const base: Estadistica = { totalReservas: items.length, reservasConfirmadas: items.filter(item => item.estado === 'CONFIRMADA').length,
      reservasCanceladas: items.filter(item => item.estado === 'CANCELADA').length, reservasPendientes: items.filter(item => item.estado === 'PENDIENTE').length,
      pasajerosConfirmados };
    if (scope === 'viaje') return { ...base, viajeId: id, cuposOfrecidos: capacity,
      cuposDisponibles: Math.max(0, capacity - pasajerosConfirmados), porcentajeOcupacion: percentage(pasajerosConfirmados, capacity) };
    return { ...base, ...(scope === 'conductor' ? { conductorId: id } : { vehiculoId: id }), viajesConsultados: included.length,
      vehiculosUtilizados: new Set(included.map(item => item.vehiculoId)).size, cuposOfrecidosAcumulados: capacity,
      porcentajeOcupacionPromedio: percentage(pasajerosConfirmados, capacity) };
  },
};
