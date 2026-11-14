import { ApiError, query, request } from './http';
import type { Conductor, Estadistica, Login, PaginaViajes, ReservasViaje, Vehiculo, VehiculoInput, Viaje, ViajeInput } from '../types';
export type Filtros = Record<string, string | number | undefined>;
export interface Api {
  me(): Promise<Conductor>;
  profile(body: {nombre: string; telefono: string | null}): Promise<Conductor>;
  vehicles(): Promise<{datos: Vehiculo[]}>;
  saveVehicle(body: VehiculoInput, id?: number): Promise<Vehiculo>;
  deactivateVehicle(id: number): Promise<void>;
  trips(filters?: Filtros): Promise<PaginaViajes>;
  trip(id: number): Promise<Viaje>;
  saveTrip(body: ViajeInput, key: string, existing?: Viaje): Promise<Viaje>;
  cancelTrip(id: number): Promise<void>;
  finishTrip(id: number): Promise<Viaje>;
  reservations(tripId: number, estado?: string): Promise<ReservasViaje>;
  stats(scope: 'conductor' | 'vehiculo' | 'viaje', id: number, filters?: Filtros): Promise<Estadistica>;
}
export const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
export const login = (correo: string, password: string) => request<Login>(base, '/auth/login', {method:'POST', body:{correo:correo.trim().toLowerCase(), password}});
export const register = (body: {nombre:string; correo:string; password:string; telefono:string|null}) => request<Conductor>(base, '/auth/registro', {method:'POST', body});
export function createApi(token: string, conductorId: number, expired: () => void): Api {
  const signed = async <T>(path: string, options: Parameters<typeof request>[2] = {}) => {
    try { return await request<T>(base, path, {...options, token}); }
    catch (error) { if (error instanceof ApiError && error.status === 401) expired(); throw error; }
  };
  const ownTrip = (trip: Viaje) => { if (trip.conductorId !== conductorId) throw new ApiError('El servicio devolvió un viaje que no corresponde a tu cuenta.', 403); return trip; };
  return {
    me: () => signed('/auth/me'),
    profile: body => signed(`/conductores/${conductorId}`, {method:'PUT', body}),
    vehicles: () => signed('/vehiculos'),
    saveVehicle: (body, id) => signed(`/vehiculos${id ? `/${id}` : ''}`, {method:id ? 'PUT' : 'POST', body}),
    deactivateVehicle: id => signed(`/vehiculos/${id}`, {method:'DELETE'}),
    trips: async filters => {
      const data = await signed<PaginaViajes>(`/viajes${query({...filters, conductorId})}`);
      data.datos.forEach(ownTrip); return data;
    },
    trip: async id => ownTrip(await signed(`/viajes/${id}`)),
    saveTrip: async (body, key, existing) => ownTrip(await signed(`/viajes${existing ? `/${existing.viajeId}` : ''}`, {
      method:existing ? 'PATCH' : 'POST', body,
      headers:existing ? {'If-Match':String(existing.version)} : {'Idempotency-Key':key},
    })),
    cancelTrip: id => signed(`/viajes/${id}`, {method:'DELETE'}),
    finishTrip: async id => ownTrip(await signed(`/viajes/${id}/finalizar`, {method:'POST'})),
    reservations: (id, estado) => signed(`/reservas/viaje/${id}${query({estado})}`),
    stats: (scope, id, filters) => signed(`/estadisticas/${scope}/${id}${query(filters ?? {})}`),
  };
}
