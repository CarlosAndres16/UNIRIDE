/** Prueba funcional real. Crea registros de prueba; nunca imprime credenciales. */
import {randomUUID} from 'node:crypto';

const args = process.argv.slice(2);
if (!args.includes('--crear-datos-de-prueba')) {
  console.error('Uso: node scripts/probar-flujo.mjs --gateway http://IP:8080 --crear-datos-de-prueba');
  console.error('Crea una cuenta, un vehículo y un viaje de prueba; finaliza el viaje y desactiva el vehículo.');
  process.exit(1);
}
const index = args.indexOf('--gateway');
const base = new URL(index >= 0 ? args[index+1] : 'http://localhost:8080');
if (!['http:','https:'].includes(base.protocol) || base.username || base.password || base.pathname !== '/' || base.search || base.hash) {
  throw new Error('--gateway debe ser un origen HTTP sin credenciales ni rutas.');
}
let token;
const creados = {};
async function call(method, path, body, extra = {}) {
  const response = await fetch(new URL(`/api/v1${path}`, base), {
    method, signal: AbortSignal.timeout(30000),
    headers: {'X-Correlation-Id':randomUUID(), ...(body ? {'Content-Type':'application/json'} : {}),
      ...(token ? {Authorization:`Bearer ${token}`} : {}), ...extra},
    ...(body ? {body:JSON.stringify(body)} : {}),
  });
  if (!response.ok) throw new Error(`${method} ${path}: HTTP ${response.status}; correlación ${response.headers.get('X-Correlation-Id') ?? 'no disponible'}`);
  return response.status === 204 ? undefined : response.json();
}
try {
  const unique = randomUUID().replaceAll('-','');
  const correo = `prueba.${unique}@example.com`;
  const password = randomUUID() + randomUUID();
  const perfil = await call('POST','/auth/registro',{nombre:'Prueba de integración UniRide',correo,password});
  creados.conductorId = perfil.conductorId;
  const login = await call('POST','/auth/login',{correo,password});
  token = login.accessToken;
  const me = await call('GET','/auth/me');
  if (me.conductorId !== perfil.conductorId) throw new Error('El perfil autenticado no coincide.');
  const vehiculo = await call('POST','/vehiculos',{placa:`T${unique.slice(0,8).toUpperCase()}`,marca:'Prueba',modelo:'Integración',color:'Gris',tipo:'Automóvil',capacidad:4});
  creados.vehiculoId = vehiculo.vehiculoId;
  const dia = new Date(); dia.setUTCDate(dia.getUTCDate()+2);
  const viaje = await call('POST','/viajes',{vehiculoId:vehiculo.vehiculoId,
    origen:{descripcion:'Origen de prueba',latitud:4.6097,longitud:-74.0817},
    destino:{descripcion:'Destino de prueba',latitud:4.612,longitud:-74.09},
    fechaSalida:dia.toISOString().slice(0,10),horaSalida:'10:00',capacidad:2}, {'Idempotency-Key':randomUUID()});
  creados.viajeId = viaje.viajeId;
  const listado = await call('GET',`/viajes?conductorId=${me.conductorId}&estado=TODOS`);
  if (!listado.datos.some(v=>v.viajeId===viaje.viajeId)) throw new Error('El viaje no aparece en la lista propia.');
  const actualizado = await call('PATCH',`/viajes/${viaje.viajeId}`,{horaSalida:'10:15'},{'If-Match':String(viaje.version)});
  const reservas = await call('GET',`/reservas/viaje/${viaje.viajeId}`);
  await call('GET',`/estadisticas/viaje/${viaje.viajeId}`);
  await call('GET',`/estadisticas/conductor/${me.conductorId}`);
  await call('GET',`/estadisticas/vehiculo/${vehiculo.vehiculoId}`);
  await call('POST',`/viajes/${viaje.viajeId}/finalizar`);
  await call('DELETE',`/vehiculos/${vehiculo.vehiculoId}`);
  console.log(JSON.stringify({resultado:'APROBADO',conductorId:me.conductorId,vehiculoId:vehiculo.vehiculoId,
    viajeId:actualizado.viajeId,reservas:reservas.total,estadoFinal:'FINALIZADO',vehiculoFinal:'INACTIVO'},null,2));
} catch (error) {
  if (Object.keys(creados).length) console.error(JSON.stringify({registrosDePruebaCreados:creados}));
  console.error(error instanceof Error ? error.message : 'Falló la prueba de integración.');
  console.error('Puede haber registros de prueba creados antes del fallo. Revisa los servicios antes de repetirla.');
  process.exitCode = 1;
}
