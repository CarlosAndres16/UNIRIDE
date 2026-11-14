export interface Conductor { conductorId: number; nombre: string; correo: string; telefono: string | null; activo: boolean }
export interface Login { accessToken: string; tokenType: string; expiresIn: number; conductorId: number }
export interface Vehiculo { vehiculoId: number; conductorId: number; placa: string; marca: string; modelo: string; color: string; tipo: string; capacidad: number; estado: 'ACTIVO' | 'INACTIVO' }
export type VehiculoInput = Pick<Vehiculo, 'placa' | 'marca' | 'modelo' | 'color' | 'tipo' | 'capacidad'>;
export interface Punto { descripcion: string; latitud: number; longitud: number }
export interface Viaje { viajeId: number; conductorId: number; vehiculoId: number; origen: Punto; destino: Punto; fechaSalida: string; horaSalida: string; capacidad: number; cuposDisponibles: number; estado: 'ACTIVO' | 'FINALIZADO' | 'CANCELADO'; version: number; fechaCreacion?: string; fechaActualizacion?: string }
export type ViajeInput = Pick<Viaje, 'vehiculoId' | 'origen' | 'destino' | 'fechaSalida' | 'horaSalida' | 'capacidad'>;
export interface PaginaViajes { datos: Viaje[]; paginacion: {pagina: number; tamano: number; totalElementos: number; totalPaginas: number} }
export interface Reserva { reservaId: number; viajeId: number; pasajeroNombre: string; cuposReservados: number; estado: 'CONFIRMADA' | 'PENDIENTE' | 'CANCELADA'; fechaReserva: string }
export interface ReservasViaje { viajeId: number; total: number; datos: Reserva[] }
export interface Estadistica { conductorId?: number; vehiculoId?: number; viajeId?: number; viajesConsultados?: number; vehiculosUtilizados?: number; totalReservas: number; reservasConfirmadas: number; reservasCanceladas: number; reservasPendientes?: number; pasajerosConfirmados: number; porcentajeOcupacionPromedio?: number; porcentajeOcupacion?: number; cuposOfrecidos?: number; cuposOfrecidosAcumulados?: number; cuposDisponibles?: number }
export type Seccion = 'inicio' | 'viajes' | 'vehiculos' | 'reservas' | 'estadisticas' | 'perfil';
