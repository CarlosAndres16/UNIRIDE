# Integración de Reservas y Estadísticas

Versión local: 1.0.0. Fuente de verdad: Contrato Técnico Unificado de UniRide.
Esta guía prepara el intercambio con los compañeros; no registra pruebas realizadas.

## Configuración compartida

| Acuerdo | Participantes |
| --- | --- |
| `JWT_SECRET` HS256 | Usuarios, Vehículos, Viajes y Reservas |
| `SERVICE_API_KEY` | Viajes y Reservas |
| URL base de Viajes | Se configura en `VIAJES_SERVICE_URL` |
| URL base de Vehículos | Se configura en `VEHICULOS_SERVICE_URL` |
| Rutas públicas de Reservas | Gateway: `/api/v1/reservas/**`, `/api/v1/estadisticas/**` |

Los secretos se acuerdan fuera del repositorio. Reservas identifica al conductor
con `sub` del JWT, exige `iat` y `exp` y no consulta Usuarios. El JWT de acceso
proviene de `POST /api/v1/auth/login` de Usuarios, implementado por su responsable.

## Operaciones consumidas

| Proveedor | Método y ruta | Autenticación |
| --- | --- | --- |
| Viajes | `GET /api/v1/viajes/{viajeId}` | Bearer del conductor |
| Viajes | `GET /api/v1/viajes` | Bearer del conductor |
| Viajes | `PUT /api/v1/viajes/{viajeId}/ocupacion` | `X-Service-Key`, sin Bearer |
| Vehículos | `GET /api/v1/vehiculos/{vehiculoId}` | Bearer del conductor |

Cada llamada incluye el mismo `X-Correlation-Id` UUID de la solicitud original.
Las llamadas son directas, sin Gateway. Las URLs son configurables y no contienen
el prefijo `/api/v1`. Se exige JSON UTF-8 y nombres camelCase.

## Objetos de respuesta esperados

`Viaje` contiene exactamente estos campos:

```text
viajeId, conductorId, vehiculoId, origen, destino,
fechaSalida, horaSalida, capacidad, cuposDisponibles, estado,
version, fechaCreacion, fechaActualizacion
```

`origen` y `destino`: `descripcion`, `latitud`, `longitud`. Fechas `YYYY-MM-DD`,
hora `HH:MM` de Bogotá y timestamps UTC. Capacidad de 1 a 8; disponibilidad entre
0 y capacidad; versión positiva. Estados `ACTIVO`, `FINALIZADO`, `CANCELADO`.

`Vehiculo` contiene exactamente:

```text
vehiculoId, conductorId, placa, marca, modelo, color, tipo, capacidad, estado
```

Estado `ACTIVO` o `INACTIVO`. Reservas permite consultar estadísticas históricas
de un vehículo propio inactivo; no aplica la restricción de crear viajes.

El listado de Viajes recibe `conductorId` o `vehiculoId`, límites de fecha
opcionales, `estado=TODOS`, `pagina` desde 1 y `tamano=50`. Responde:

```json
{
  "datos": [],
  "paginacion": {
    "pagina": 1,
    "tamano": 50,
    "totalElementos": 0,
    "totalPaginas": 0
  }
}
```

Reservas recorre todas las páginas, comprueba consistencia y duplicados, filtra
viajes cancelados al agregar y valida que los resultados correspondan al dueño,
vehículo y período solicitados. No entrega resultados parciales ante fallos.

El PUT interno recibe `{"cuposOcupados": 2}` con el total confirmado y responde:

```text
viajeId, capacidad, cuposDisponibles, estado, version, fechaActualizacion
```

Repetir el mismo total es idempotente. Solo se informa para viajes activos.
Un total superior a capacidad debe producir 400 en Viajes; Reservas conserva el
total real y registra el rechazo sin hacer fallar la consulta del conductor.

## Errores y fallos

Los proveedores deben responder el `ErrorResponse` común: `timestamp`, `status`,
`error`, `message`, `path`, `correlationId`, más `detalles` para 400. Los códigos
404 distinguen `VIAJE_NO_ENCONTRADO` y `VEHICULO_NO_ENCONTRADO`.

Reservas conserva los errores de dominio válidos y transforma caídas, timeouts,
5xx agotados y DTO inválidos en 503. Solo el Gateway genera 504. El timeout es
3000 ms por intento y se permite un reintento en GET y en PUT de ocupación.
Si falla únicamente el informe de ocupación, la consulta válida se conserva y
una consulta posterior permite reintentarlo.

## Datos para el intercambio real

Los IDs 25, 12, 305 y las reservas del seed pertenecen al escenario local. Antes
de sustituir mocks, se necesitan IDs reales coherentes de conductor, vehículo y
viaje. No se modifican automáticamente las reservas existentes para adaptar IDs.
La API versión 1 no crea ni actualiza reservas.

La ocupación se reconcilia durante las consultas autorizadas, sin cache ni
dependencia de un proceso anterior del mock. Un cambio directo en SQL no provoca
HTTP en ese instante; se detecta en una consulta posterior.

## Definiciones que conviene confirmar con el equipo

- El contrato no define la ponderación del promedio. La implementación usa
  pasajeros confirmados acumulados / capacidades acumuladas, redondeo a dos
  decimales y límite 0–100. El número real de pasajeros nunca se recorta.
- Sin límites de fecha, `periodo=null`; un límite omitido dentro de un período
  parcial se representa con `null`.
- El contrato no asigna código de dominio a un 404 de ruta ni a 405; se conserva
  provisionalmente el error de enrutamiento nativo con UUID de correlación.

## Pendiente para cerrar la integración

Se requieren los secretos acordados, URLs reales accesibles, un token emitido
por Usuarios, IDs coherentes y el enrutamiento del Gateway. Las pruebas finales
locales se ejecutaron con 232 casos y 261 subcasos aprobados, incluyendo lecturas
de SQL Server real. Las dependencias HTTP de esas pruebas son simuladas: el
intercambio con los servidores reales del equipo sigue pendiente.
