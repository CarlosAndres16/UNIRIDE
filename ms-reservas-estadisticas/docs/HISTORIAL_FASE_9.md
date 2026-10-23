# Historial hasta fase 9 — UniRide Reservas y Estadísticas

Este documento conserva el estado anterior a la ampliación final. Para ejecutar
la versión actual consulta el README de la raíz; los resultados históricos de
pruebas no certifican los cambios posteriores a la fase 9.

Responsable: Juan Alejandro Apache Moreno.

Microservicio `ms-reservas-estadisticas`, puerto 8084, desarrollado por fases.
Se sigue el «Contrato Técnico Unificado» recibido y las instrucciones del TXT.
Por indicación del responsable se utiliza **Python 3.13.2**, ya instalado.

## Estado actual: fase 9

- Entorno `.venv` recreado con Python 3.13.2 y dependencias reinstaladas.
- SQL Express en ejecución: `DESKTOP-LLK6D0L\SQLEXPRESS`.
- ODBC Driver 18 de 64 bits instalado.
- Base propia `unirride_reservas` con `dbo.reservas` y la tabla técnica
  `dbo.alembic_version`.
- Login SQL `unirride_reservas_app` creado; contraseña aleatoria solo en `.env`.
- Roles locales: `db_datareader`, `db_datawriter` y `db_ddladmin`, para consultas,
  el futuro seed y las futuras migraciones. Sin roles de servidor ni permisos
  concedidos en bases ajenas.
- Configuración y conexión diferida con pydantic-settings, SQLAlchemy 2.x y pyodbc.
- Modo mixto habilitado y SQL Express reiniciado con autorización del responsable.
- Conexión real con `unirride_reservas_app` verificada con código de salida 0.
  El puerto TCP se mantiene en 29178.
- Modelo `Reserva` y enum `EstadoReserva` implementados.
- Primera migración `0001_crear_reservas` aplicada y en `head`.
- `alembic check` no detecta operaciones pendientes. La inspección de catálogos
  verifica la estructura de `dbo.reservas`.
- Seed del viaje 305 cargado: Laura Gómez y David Ruiz CONFIRMADA, Carlos Pérez
  CANCELADA; un cupo cada uno y fechas fijas UTC.
- Dos ejecuciones verificadas: primera `creadas=3, existentes=0`; segunda
  `creadas=0, existentes=3`, conservando los mismos IDs y valores.
- Arquitectura HTTP incorporada: `ErrorResponse`, excepciones de aplicación,
  manejadores globales, middleware `X-Correlation-Id` y logging en UTC.
- Verificación HTTP aislada, sin consultas SQL ni llamadas a otros servicios.
- Validador JWT HS256 y dependencia de autenticación preparados para las futuras
  rutas, con identificación del conductor desde `sub` y comprobación de dueño.
- El secreto real del equipo sigue pendiente de configuración privada. Las
  pruebas JWT utilizan claves aleatorias temporales, sin modificar `.env`.
- Fase 6 verificada: 26 pruebas JWT correctas y 20 pruebas HTTP de regresión
  correctas. La integración con un token real de Usuarios queda pendiente.
- Mocks locales de Viajes (8083) y Vehículos (8082), con estado solo en memoria,
  autenticación, datos de ejemplo y las cuatro operaciones que consume Reservas.
- Arranque real de ambos mocks comprobado en sus puertos; los procesos
  temporales de prueba se detuvieron al terminar.
- Fase 7 verificada: 27 pruebas de mocks correctas, más las 46 regresiones de
  HTTP y JWT. También pasó la comprobación por HTTP real en 8083 y 8082.
- Clientes asíncronos de Viajes y Vehículos implementados, con límites HTTP,
  reintento, credenciales por operación y validación de los objetos recibidos.
- DTO compartidos entre clientes y mocks, sin dependencia del código de
  producción hacia `mocks/`.
- Fase 8 verificada: 30 pruebas de clientes y las 73 anteriores correctas,
  103 en total. También pasó HTTP real con mocks temporales independientes.
- Primer endpoint de Reservas implementado: consulta por viaje con JWT,
  validación del propietario y filtro opcional por estado.
- Fase 9 verificada: 18 pruebas nuevas y las 103 anteriores correctas,
  121 en total; lectura real del seed en SQL Server también comprobada.

Comprobaciones de las fases anteriores: dependencias compatibles, configuración
y URL sin exponer contraseñas, preparación repetible sin duplicar objetos y
consulta administrativa sobre la base propia, vacía en ese momento. FastAPI arrancó
con Python 3.13 en un puerto local temporal: `/docs` y `/openapi.json` respondieron
200, y `/` respondió 404. El proceso temporal de comprobación se detuvo al acabar.
Tras el reinicio autorizado, la comprobación con la cuenta SQL propia también
terminó correctamente sobre SQL Server 16.0.1000.6, usando Python 3.13.2.

## Entorno Python y dependencias

El entorno anterior se conservó en
`X:\Proyecto Uniride\.setup\venv-python312-phase1`. Para restaurarlo tendría que
volver a su ubicación original; los entornos virtuales no son portables.

Para reproducir el entorno en una copia nueva:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe --version
```

Se puede activar con `.\.venv\Scripts\Activate.ps1`, pero los comandos de esta
guía utilizan directamente su intérprete para evitar problemas de activación.

## Configuración

`app/config/settings.py` lee las variables del proceso y el `.env` de la raíz.
`SERVER_PORT`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` y
`DB_DRIVER` son obligatorias. La contraseña utiliza `SecretStr`; no se imprime.
El `.env` real está excluido por `.gitignore`: no lo sobrescribas con el ejemplo.

El `.env.example` usa 1433 como puerto típico. Esta instancia SQL Express utiliza
el puerto dinámico **29178**, guardado en `.env`. Si cambia al reiniciar, actualiza
`DB_PORT` con el puerto real de la instancia.

`JWT_SECRET` debe contener el mismo valor privado en los cuatro microservicios.
En este equipo sigue pendiente; no se inventó una llave para sustituir la del
equipo. `SERVICE_API_KEY` también está pendiente y se necesita para probar el
PUT de ocupación del mock; debe coincidir entre Reservas y Viajes. Las URLs
`VIAJES_SERVICE_URL` y `VEHICULOS_SERVICE_URL`, y las opciones `HTTP_TIMEOUT_MS=3000`
y `HTTP_MAX_RETRIES=1`, están previstas en el ejemplo para esas fases.

## Preparar la base y la cuenta

Este paso ya se ejecutó en este equipo. En otra instalación, configura antes
`.env` con una contraseña fuerte privada y ejecuta con una cuenta Windows
administradora de la instancia:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.preparar_base_datos
```

El script usa SQLAlchemy y autenticación Windows para preparar la base, el login
y el usuario si faltan. Conserva los existentes y sus contraseñas. SQLAlchemy
delimita los identificadores y escapa el literal de contraseña del DDL.
No crea tablas, no cambia el modo de autenticación y no reinicia servicios.
La aplicación utiliza `DB_USER` y `DB_PASSWORD`; necesita que la instancia
admita autenticación SQL (modo mixto), habilitada y verificada en este equipo.

## Comprobar la conexión de la aplicación

Para comprobar la conexión:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.verificar_conexion
$LASTEXITCODE
```

El resultado correcto termina con código 0 y muestra la base, el login SQL,
la versión del servidor y el número de tablas. Después de la fase 3 hay 2:
`reservas` y la tabla técnica `alembic_version`.
Un fallo termina con código 1 y un diagnóstico sin secretos.

La URL `mssql+pyodbc` se construye con `URL.create`, sin concatenar credenciales.
Se cifra la conexión y se permite `TrustServerCertificate=yes` para desarrollo
local. El engine y las sesiones son diferidos: importar o iniciar FastAPI no
abre conexiones SQL. La aplicación puede arrancar aunque SQL Server esté caído.

## Modelo y migraciones: fase 3

`app/models/base.py` declara los metadatos. `app/models/reserva.py` define el
modelo `Reserva`, el enum y el conversor UTC. Los atributos Python son camelCase
y se mapean explícitamente a las columnas snake_case de SQL Server.

| Columna | Tipo | Regla |
| --- | --- | --- |
| `id` | `INT IDENTITY(1,1)` | Clave primaria |
| `viaje_id` | `INT` | Obligatorio y positivo; sin FK a otros servicios |
| `pasajero_nombre` | `NVARCHAR(150)` | Obligatorio y no vacío tras quitar espacios |
| `cupos_reservados` | `INT` | Obligatorio, al menos 1 |
| `estado` | `NVARCHAR(20)` | PENDIENTE, CONFIRMADA o CANCELADA |
| `fecha_reserva` | `DATETIME2(6)` | Obligatorio, interpretado siempre como UTC |

El estado distingue mayúsculas y rechaza espacios finales. El índice no único
`ix_reservas_viaje_estado` cubre `(viaje_id, estado)`. No se impone unicidad de
pasajero ni un límite de capacidad que corresponde al servicio Viajes.

SQL Server usa `SYSUTCDATETIME()` si no se especifica una fecha. Si se proporciona
una fecha desde Python, debe incluir zona horaria: `UtcDateTime` la normaliza a
UTC, la guarda sin zona en DATETIME2 y devuelve una fecha con zona UTC al leerla.
Se rechazan fechas Python sin zona para evitar asumir la hora del equipo.

Alembic toma la conexión de Settings, sin contraseñas en `alembic.ini`.
`alembic/env.py` carga los modelos y `alembic/versions/0001_crear_reservas.py`
guarda la definición inicial de la tabla. La tabla `alembic_version` registra
la revisión aplicada; no almacena estadísticas ni reservas.

Aplicar migraciones en una instalación nueva o repetir el comando sin duplicar:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Para comprobar esta fase:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m scripts.verificar_estructura
$LASTEXITCODE
```

Se espera `0001_crear_reservas (head)`, `No new upgrade operations detected`,
`Estructura dbo.reservas correcta` y código final 0. El total era 0 al terminar
la fase 3; después de cargar los ejemplos de la fase 4 es 3.
El verificador inspecciona tipos, precisión, nulabilidad, identidad, PK, nombres
y activación de CHECK, índice y ausencia de FK. No prueba inserciones rechazadas:
no inserta ni borra filas, ni consume valores de identidad durante la verificación.

También puedes consultar desde SSMS, dentro de `unirride_reservas`:

```sql
SELECT version_num FROM dbo.alembic_version;
SELECT COUNT(*) AS totalReservas FROM dbo.reservas;
```

Para revisar el SQL de una actualización sin ejecutarlo:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

## Datos de prueba: fase 4

`scripts/seed_reservas.py` carga los siguientes ejemplos en una sola transacción:

| Viaje | Pasajero | Cupos | Estado | Fecha UTC |
| --- | --- | --- | --- | --- |
| 305 | Laura Gómez | 1 | CONFIRMADA | 2026-10-01T14:20:00Z |
| 305 | David Ruiz | 1 | CONFIRMADA | 2026-10-01T14:21:00Z |
| 305 | Carlos Pérez | 1 | CANCELADA | 2026-10-01T14:22:00Z |

Los IDs se asignan mediante IDENTITY, sin imponer números desde el script.
La carga se ejecutó y se comprobó dos veces en este equipo: permanecen 3 filas,
con IDs 1, 2 y 3, y las mismas fechas y valores tras la segunda ejecución.

Para ejecutar o repetir la carga:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.seed_reservas
$LASTEXITCODE
```

Como los ejemplos ya están cargados, se espera:

```text
Carga completada: creadas=0, existentes=3.
0
```

Cada ejemplo se identifica por viaje, nombre y fecha fija UTC. Si ya existe,
el script lo conserva sin modificar sus cupos o estado. No borra filas, no
reinicia identidades y no reemplaza otras reservas. La consulta de existencia
usa `UPDLOCK, HOLDLOCK` durante la transacción para coordinar ejecuciones de este
seed; no crea una restricción UNIQUE global sobre los pasajeros.

El script verifica que la conexión apunta a `unirride_reservas` antes de escribir.
Usa SQLAlchemy y la configuración de `.env`, y no muestra contraseñas en los
errores. No crea tablas, no expone endpoints ni consulta otros microservicios.

Para comprobar los datos desde SQL Server Management Studio:

1. Conecta a `DESKTOP-LLK6D0L\SQLEXPRESS` con tu acceso habitual.
2. Abre `scripts/verificar_seed_ssms.sql` con **Archivo > Abrir > Archivo**.
3. Ejecuta con **F5**.

Se esperan tres filas en la primera consulta; la segunda muestra
`totalReservas=3`, `reservasConfirmadas=2`, `reservasCanceladas=1` y
`pasajerosConfirmados=2`. La tercera consulta no devuelve duplicados.
Estas consultas se comprobaron directamente contra SQL Server. Las fechas que
muestra DATETIME2 en SSMS representan UTC, aunque no incluyan el sufijo Z.

## Ejecutar FastAPI

Si sigue abierta la terminal del servidor anterior, detenlo con `Ctrl+C` antes
de iniciar el proceso actualizado:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m app.main
```

El puerto se lee de `SERVER_PORT` y Uvicorn utiliza su host local predeterminado.
La recarga automática está habilitada. Ejecuta desde la carpeta que contiene
`app` para evitar `ModuleNotFoundError`. En otra ventana:

```powershell
(Invoke-WebRequest 'http://localhost:8084/docs').StatusCode
(Invoke-RestMethod 'http://localhost:8084/openapi.json').info
curl.exe -i 'http://localhost:8084/'
```

`/docs` y `/openapi.json` responden 200. `/` devuelve 404 esperado porque no se
define una ruta raíz. Swagger todavía no contiene operaciones de negocio.

## Arquitectura HTTP: fase 5

`crearAplicacion()` construye FastAPI y registra los manejadores y el middleware.
Las comprobaciones añaden rutas únicamente a instancias de prueba; al cerrar
la fase 5 la aplicación principal aún no tenía operaciones de negocio. HTTPX se utiliza en esta fase para
verificar HTTP dentro del proceso. Los clientes de Viajes y Vehículos corresponden
a la fase 8.

Cada solicitud recibe un identificador UUID:

- Si falta `X-Correlation-Id`, se genera uno nuevo.
- Si llega un único UUID válido, se conserva su valor en formato canónico
  (minúsculas y guiones).
- Un valor vacío, inválido o un header duplicado produce 400 `FORMATO_INVALIDO`.
  Se genera un UUID nuevo para rastrear ese error; el valor rechazado no se copia
  en el cuerpo ni en los logs.
- El identificador vuelve en `X-Correlation-Id` y en los errores de aplicación.
  Un `ContextVar` lo mantiene aislado entre solicitudes concurrentes y se limpia
  al terminar cada solicitud.

`ErrorResponse` contiene exactamente los campos del contrato. `timestamp` usa
UTC con sufijo `Z`. Todos los errores 400 incluyen `detalles`, que puede ser una
lista vacía; los demás estados omiten ese campo. Ejemplo de header inválido:

```json
{
  "timestamp": "2026-10-21T20:22:53.239931Z",
  "status": 400,
  "error": "FORMATO_INVALIDO",
  "message": "X-Correlation-Id debe contener un unico UUID valido.",
  "path": "/docs",
  "correlationId": "f49d0635-ab81-443b-9dde-78df75de268d",
  "detalles": [
    {
      "campo": "X-Correlation-Id",
      "problema": "Debe enviarse una sola vez y contener un UUID valido."
    }
  ]
}
```

Las excepciones controladas validan la correspondencia entre código y estado
HTTP. La validación de entrada de FastAPI responde 400 con campos y problemas
públicos, sin copiar valores recibidos. Los errores inesperados responden 500
`ERROR_INTERNO` con un mensaje genérico. Un timeout expresado como HTTP 504 se
traduce a 503 `SERVICIO_DEPENDIENTE_NO_DISPONIBLE`.

Los logs `uniride.*` incluyen hora UTC, nivel y `correlationId`. Cada solicitud
registra método, ruta, estado y duración. Se omiten query strings, headers,
cuerpos y mensajes internos de excepciones. El arranque documentado desactiva
el access log de Uvicorn para evitar una segunda salida con la URL completa.
Un fallo antes de iniciar la respuesta se convierte en el error 500 público.
Si el fallo ocurre después de enviar los headers, ya no puede sustituirse el
cuerpo: se interrumpe la respuesta con una excepción saneada que incluye el UUID.

**Límite pendiente del contrato:** no se define un código para una ruta que no
existe ni para un método HTTP no permitido. Esos 404/405 de enrutamiento conservan
provisionalmente el JSON nativo `{"detail": "..."}` y sí devuelven
`X-Correlation-Id`. Los 404 de dominio utilizan el código específico de viaje,
reserva o vehículo dentro de `ErrorResponse`.

Comprobación automática de la fase:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.verificar_http
$LASTEXITCODE
```

Se espera `OK` y código 0. Se comprueban UUID, errores del contrato, validación,
privacidad, concurrencia de diez solicitudes y restauración del contexto.
Las rutas auxiliares no se agregan a la aplicación de producción.

Con FastAPI en ejecución, prueba desde otra ventana de PowerShell:

```powershell
curl.exe -i -H 'X-Correlation-Id: 5b9c2e7d-1171-4b93-a2aa-91af32d6b709' 'http://localhost:8084/docs'
curl.exe -i -H 'X-Correlation-Id: no-es-un-uuid' 'http://localhost:8084/docs'
```

La primera respuesta debe ser 200 y devolver el UUID enviado. La segunda debe
ser 400 `FORMATO_INVALIDO`, con un UUID nuevo idéntico en el header y en el JSON.
Los logs deben mostrar el mismo UUID de cada respuesta.

## Seguridad JWT: fase 6

`app/security/jwt_service.py` implementa la validación local con PyJWT. Se fija
`algorithms=["HS256"]`; nunca se elige el algoritmo desde el token recibido.
Se verifican la firma, la expiración y que `iat` no esté en el futuro, sin margen
adicional de reloj. Si aparece `nbf`, PyJWT también comprueba su vigencia.

Los claims `sub`, `iat` y `exp` son obligatorios. `sub` debe ser texto decimal
ASCII que represente un entero positivo; se convierte a `conductorId`. `iat` y
`exp` deben ser enteros JSON, sin convertir cadenas, booleanos ni decimales, y
`exp` debe ser posterior a `iat`. Los 3600 segundos del contrato corresponden a
la emisión en Usuarios; este consumidor verifica las fechas recibidas. No se
exigen roles, `iss`, `aud` ni otros claims ajenos al contrato, ni se consulta a
Usuarios para identificar al conductor.

`getConductorAutenticado` es la dependencia que utilizarán los cinco endpoints
en sus fases. Primero comprueba que haya un único header `Authorization` con
esquema Bearer; después valida el JWT. Devuelve un `ConductorAutenticado` interno
con el identificador y el token como `SecretStr`, oculto en su representación.
El token queda disponible para reenviarlo en los clientes de la fase 8.

Un token ausente, inválido, alterado, vencido o firmado con otra clave produce
401 `NO_AUTENTICADO`, con `WWW-Authenticate: Bearer`. Los motivos internos no se
incluyen en el JSON ni en logs. `verificarPropietario` compara el dueño del
recurso con el conductor autenticado y produce 403 `NO_AUTORIZADO` si difieren.
El dueño deberá obtenerse del recurso validado, nunca de una afirmación del
cliente. Todas estas respuestas usan `ErrorResponse` y la correlación de fase 5.

`JwtSettings` está separado de la configuración SQL. Lee `JWT_SECRET` del
entorno o del `.env`, lo almacena como `SecretStr` y rechaza ausencia, cadena
vacía o solo espacios. Se carga al utilizar la autenticación, de modo que no
exige seguridad JWT para ejecutar migraciones o comprobar SQL. Con un Bearer
presente y configuración ausente, la autenticación falla con 500 `ERROR_INTERNO`;
no se acepta el token ni se atribuye el problema de configuración al conductor.

En el `.env` local, completa únicamente `JWT_SECRET` con el valor compartido
privadamente por el equipo. Conserva las demás variables. No lo pegues en el
chat, no lo añadas a `.env.example` y no lo subas al repositorio. Reinicia el
servidor después de cambiarlo, porque la configuración se guarda en caché.

Para comprobar su presencia sin mostrar su valor:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.verificar_configuracion_jwt
$LASTEXITCODE
```

Se espera `JWT_SECRET configurado. Su valor permanece oculto.` y código 0.
Mientras falte, el script explica que está pendiente y termina con código 1.
Que exista un valor no demuestra que coincida con el de los otros servicios;
esa integración se comprobará con un token real de Usuarios posteriormente.

Para comprobar la implementación sin necesitar el secreto del equipo:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.verificar_jwt
$LASTEXITCODE
```

Se espera `Ran 26 tests`, `OK` y código 0. Las comprobaciones crean claves efímeras, JWT de
prueba y rutas protegidas en aplicaciones aisladas; no leen ni modifican el
secreto real, no consultan SQL y no realizan llamadas HTTP a otros servicios.
Al cerrar la fase 6, la aplicación principal conservaba `/docs` y `/openapi.json`
públicos sin rutas de negocio. No hay endpoint de login ni de emisión de tokens en Reservas.

## Mocks de Viajes y Vehículos: fase 7

Los módulos de `mocks/` reproducen el subconjunto de los contratos que utiliza
Reservas. Cada aplicación tiene sus propios datos en memoria, con un solo worker.
Los cambios de ocupación se conservan durante ese proceso y se restablecen al
reiniciarlo. El puerto y el host de cada mock se obtienen de su URL del entorno:
`VIAJES_SERVICE_URL` y `VEHICULOS_SERVICE_URL`. `SERVER_PORT` continúa siendo el
puerto de Reservas.

| Mock | Operación | Autenticación |
| --- | --- | --- |
| Viajes, 8083 | `GET /api/v1/viajes/{viajeId}` | JWT; solo detalle propio |
| Viajes, 8083 | `GET /api/v1/viajes` | JWT; búsqueda abierta a conductores autenticados |
| Viajes, 8083 | `PUT /api/v1/viajes/{viajeId}/ocupacion` | Solo `X-Service-Key` |
| Vehículos, 8082 | `GET /api/v1/vehiculos/{vehiculoId}` | JWT; solo vehículo propio |

Los objetos devueltos usan los campos del contrato: Viaje tiene 13 campos,
Vehículo 9 y la respuesta de ocupación 6. `horaSalida` usa `HH:MM` y las marcas
de tiempo completas se serializan en UTC con `Z`. Todos los endpoints usan
los manejadores y el middleware de correlación existentes. Se incorporó al
catálogo compartido el código contractual 409
`OPERACION_NO_PERMITIDA_POR_ESTADO`, requerido por el PUT del mock.

Datos incorporados:

| Viaje | Conductor | Vehículo | Fecha | Estado |
| --- | --- | --- | --- | --- |
| 305 | 25 | 12 | 2026-10-25 | ACTIVO; capacidad 4 y disponibles 2 |
| 306 | 25 | 12 | 2026-10-01 | FINALIZADO |
| 307 | 25 | 12 | 2026-10-31 | CANCELADO |
| 308 | 25 | 13 | 2026-10-26 | ACTIVO; capacidad 2 |
| 309 | 26 | 14 | 2026-10-27 | ACTIVO; recurso ajeno al conductor 25 |
| 1000–1050 | 27 | 16 | 2026-10-25 | 51 viajes ACTIVO, con horas diferentes |

Los vehículos 12, 13 y 15 pertenecen al conductor 25; 15 está INACTIVO. El 14
pertenece a 26 y el 16 a 27. El vehículo 12 coincide con el ejemplo del TXT.
Estos datos del mock son independientes de las tres reservas del seed SQL.

La búsqueda aplica `conductorId`, `vehiculoId`, `desde`, `hasta` y `estado`
antes de paginar. Las fechas filtran `fechaSalida`, con límites inclusivos.
`estado` admite ACTIVO (predeterminado), FINALIZADO, CANCELADO y TODOS;
`pagina` empieza en 1 y `tamano` usa 20 por defecto, con máximo 50. Los viajes
se ordenan por `viajeId`. Sin coincidencias devuelve 200, `datos: []` y
`totalPaginas: 0`. Pedir una página fuera de los resultados devuelve una lista
vacía y conserva los totales de la búsqueda.

El PUT recibe exclusivamente `cuposOcupados`, un entero entre 0 y la capacidad.
Representa el total: calcula `cuposDisponibles = capacidad - cuposOcupados`.
Un cambio incrementa `version` y actualiza `fechaActualizacion`; repetir el
mismo total conserva ambos. Un viaje no ACTIVO responde 409. La operación
requiere la llave interna y puede ejecutarse sin JWT.

Para comprobar toda la fase sin configurar secretos ni iniciar servidores:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.verificar_mocks
$LASTEXITCODE
```

Se espera `Ran 27 tests`, `OK` y código 0. Se usan claves efímeras y aplicaciones
aisladas. Las 20 comprobaciones HTTP y las 26 de JWT anteriores también pasaron.
La comprobación adicional por HTTP real verificó GET autenticados, 401,
correlación, paginación 50+1 y PUT idempotente en 8083/8082; detuvo únicamente
los procesos temporales que había creado.

### Iniciar los mocks manualmente

Para peticiones autenticadas configura privadamente en `.env`:

- `JWT_SECRET`: el mismo valor compartido por los cuatro servicios.
- `SERVICE_API_KEY`: el mismo valor compartido por Reservas y Viajes.

Ambos siguen pendientes en este equipo. Los verificadores automáticos funcionan
sin esos valores reales. Los mocks pueden abrir Swagger, pero para responder a
peticiones con credenciales necesitan su configuración privada correspondiente.
El PUT utiliza solo la configuración de la llave interna, independiente de JWT.
Reinicia los procesos cuando cambies la configuración.

En una terminal PowerShell:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m mocks.viajes_mock
```

En otra terminal:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m mocks.vehiculos_mock
```

Abre [Swagger de Viajes](http://localhost:8083/docs) y
[Swagger de Vehículos](http://localhost:8082/docs). `Ctrl+C` detiene cada mock.

En una tercera terminal, con `JWT_SECRET` ya configurado, crea un token de
prueba local y guárdalo en una variable:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
$token = .\.venv\Scripts\python.exe -m scripts.generar_jwt_mock --conductor-id 25
if ($LASTEXITCODE -ne 0) { throw 'Revisa la configuracion de JWT_SECRET.' }
$headers = @{
    Authorization = "Bearer $token"
    'X-Correlation-Id' = [guid]::NewGuid().ToString()
}
Invoke-RestMethod 'http://localhost:8083/api/v1/viajes/305' -Headers $headers
Invoke-RestMethod 'http://localhost:8082/api/v1/vehiculos/12' -Headers $headers
```

`generar_jwt_mock` es una utilidad de desarrollo local, con `sub`, `iat`, `exp`
y vigencia 3600 s. En la integración real el token lo emitirá Usuarios mediante
su login. El helper no agrega rutas de autenticación a Reservas ni a los mocks.

Para comprobar las dos páginas con el mismo conductor autenticado (la búsqueda
es abierta):

```powershell
$pagina1 = Invoke-RestMethod 'http://localhost:8083/api/v1/viajes?conductorId=27&estado=TODOS&pagina=1&tamano=50' -Headers $headers
$pagina2 = Invoke-RestMethod 'http://localhost:8083/api/v1/viajes?conductorId=27&estado=TODOS&pagina=2&tamano=50' -Headers $headers
$pagina1.datos.Count
$pagina2.datos.Count
```

Se esperan 50 y 1. El detalle del viaje 309 o del vehículo 14, con el JWT de 25,
debe responder 403; un id inexistente responde 404 con su código específico.

Para probar ocupación, introduce la llave privada en el prompt local oculto:

```powershell
$llaveSegura = Read-Host 'SERVICE_API_KEY compartida con Viajes' -AsSecureString
$llave = [System.Net.NetworkCredential]::new('mock', $llaveSegura).Password
$headersInternos = @{'X-Service-Key' = $llave}
$ocupacion1 = Invoke-RestMethod 'http://localhost:8083/api/v1/viajes/305/ocupacion' -Method Put -Headers $headersInternos -ContentType 'application/json' -Body '{"cuposOcupados":3}'
$ocupacion2 = Invoke-RestMethod 'http://localhost:8083/api/v1/viajes/305/ocupacion' -Method Put -Headers $headersInternos -ContentType 'application/json' -Body '{"cuposOcupados":3}'
$ocupacion1
$ocupacion2
Remove-Variable token, headers, llave, llaveSegura, headersInternos
```

Ambas respuestas deben tener `cuposDisponibles=1`, igual `version` e igual
`fechaActualizacion`. En un proceso recién iniciado esa versión será 2.

## Clientes HTTP: fase 8

`ViajesClient` y `VehiculosClient` consultan directamente las APIs de los otros
servicios, con sesiones asíncronas HTTPX. Sus URLs vienen de `.env`; cambiar de
los mocks a los servicios reales requiere configurar esas URLs. Los objetos
del contrato están en `app/schemas/integracion_schema.py`. Los mocks importan
ese contrato mediante alias, por lo que los clientes no necesitan importar
código de prueba.

| Cliente y método | Operación |
| --- | --- |
| `ViajesClient.obtenerViaje` | GET del detalle de un viaje |
| `ViajesClient.listarViajes` | GET de una página, con `estado=TODOS` y `tamano=50` |
| `ViajesClient.listarTodosLosViajes` | Recorre todas las páginas con los mismos filtros |
| `ViajesClient.actualizarOcupacion` | PUT interno del total de cupos ocupados |
| `VehiculosClient.obtenerVehiculo` | GET del detalle de un vehículo |

Los GET reciben el contexto `ConductorAutenticado` de la fase 6 y reenvían su
JWT en `Authorization: Bearer`. El PUT envía únicamente `X-Service-Key`, leído
de `SERVICE_API_KEY` cuando se utiliza esa operación. Todos reenvían el UUID
del contexto o el UUID explícito normalizado; si se utilizan fuera de una
solicitud y no se proporciona uno, generan un identificador para la operación.
El recorrido completo conserva el mismo UUID en todas las páginas y reintentos.

`HttpClientSettings` es independiente de SQL y JWT. Lee las dos URLs base y:

```dotenv
HTTP_TIMEOUT_MS=3000
HTTP_MAX_RETRIES=1
```

El máximo de reintentos permitido es 1; puede deshabilitarse con 0. HTTPX limita
conexión, lectura, escritura y espera de conexión a 3 segundos; un límite
asíncrono adicional fija también 3 segundos totales de espera de red por intento.
Una llamada puede realizar como máximo dos intentos. Las dependencias
`getViajesClient` y `getVehiculosClient` crean y cierran sus sesiones incluso
si ocurre un error. El transporte predeterminado no añade reintentos propios.

El reintento se aplica a GET y al PUT idempotente de ocupación ante fallos de
transporte, timeout, HTTP 5xx y JSON o DTO 200 inválidos. El mismo total, JWT o
llave y UUID se conservan al repetir. Las redirecciones se rechazan como 503,
sin seguir su destino ni reenviar credenciales a otra ubicación.

Tratamiento de respuestas:

| Respuesta del proveedor | Resultado del cliente |
| --- | --- |
| 200 y objeto válido | DTO del contrato |
| 401, 403 o 404 con `ErrorResponse` válido | Conserva estado y código, sin reintentar |
| 400 contractual válido | Conserva estado y código, con detalles públicos controlados |
| 409 contractual válido en PUT ocupación | Conserva el conflicto, sin reintentar |
| 409 en GET u otro estado inesperado | 503, sin reintentar ese 4xx |
| Error 4xx con HTML, JSON incompleto o código incoherente | 503, sin interpretar que el recurso no existe |
| Timeout, conexión fallida, HTTP 5xx o DTO 200 inválido persistentes | 503 tras el reintento permitido |

Los clientes comprueban tipos, campos obligatorios, estados, formato de fechas,
horas y timestamps con zona, y límites de capacidad y disponibilidad. El id
devuelto debe coincidir con el solicitado; un objeto incoherente produce 503.
El propietario del detalle se compara defensivamente con el conductor del JWT;
si difiere se responde 403. Un vehículo propio INACTIVO sigue siendo válido
para consultar estadísticas históricas.

La paginación filtra por conductor, vehículo y fechas inclusivas. Se verifica
la página devuelta, tamaño, cantidad de elementos y total de páginas. El
recorrido completo rechaza ids repetidos y cambios de totales entre páginas,
para no entregar resultados parciales o mezclar conteos de búsquedas distintas.
Conserva los viajes CANCELADO: su exclusión pertenece al cálculo estadístico de
las fases correspondientes.

Los errores del proveedor se validan antes de propagarlos: se exigen todos los
campos externos, con `detalles` como lista en 400. El consumidor usa mensajes y
detalles controlados, sin copiar cuerpos, mensajes privados o credenciales del
proveedor. El `ErrorResponse` final mantiene la ruta y la correlación de la
solicitud recibida por Reservas. Los logs incluyen dependencia, método, estado,
intento y UUID; no registran tokens, llaves ni cuerpos.

Para comprobar la fase:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.verificar_clientes
$LASTEXITCODE
```

El resultado correcto termina en `Ran 30 tests`, `OK` y código 0. El verificador usa transportes
HTTPX simulados y los mocks en memoria con claves efímeras; funciona sin SQL,
servidores en ejecución ni los secretos privados del equipo. Se comprobó además
HTTP real con dos mocks temporales: detalles, 51 viajes y PUT idempotente; esos
procesos temporales se detuvieron conservando los servidores del usuario.

El método PUT está preparado en el cliente. La fase 14 decidirá cuándo informar
la ocupación y cómo conservar una consulta válida si esa actualización falla.
Los GET actuales del cliente no ejecutan PUT. La fase 8 preparó clientes
internos; la fase 9 incorpora el primer endpoint de Reservas a Swagger.

## Reservas por viaje: fase 9

```http
GET /api/v1/reservas/viaje/{viajeId}
Authorization: Bearer <JWT>
X-Correlation-Id: <UUID opcional>
```

`estado` es un filtro opcional con los valores PENDIENTE, CONFIRMADA y CANCELADA.
El identificador debe ser un entero positivo. El controlador utiliza la
autenticación de fase 6 y delega en `ReservaService`.

El servicio consulta primero Viajes con el JWT y UUID de la solicitud. Verifica
el identificador y el propietario del viaje. Solo después utiliza
`ReservaRepository` para consultar `dbo.reservas`. La sesión SQL se prepara de
forma diferida; lectura y conversión de entidades a DTO se ejecutan en un
threadpool para mantener libre el event loop. Cada solicitud tiene su sesión,
que se cierra al finalizar.

La consulta usa SQLAlchemy con parámetros, filtra por viaje y estado si se
proporciona, y ordena por id. El resultado incluye únicamente:

```json
{
  "viajeId": 305,
  "total": 1,
  "datos": [
    {
      "reservaId": 1,
      "viajeId": 305,
      "pasajeroNombre": "Laura Gómez",
      "cuposReservados": 1,
      "estado": "CONFIRMADA",
      "fechaReserva": "2026-10-01T14:20:00Z"
    }
  ]
}
```

Este JSON ilustra una reserva; la consulta completa del seed del viaje 305
devuelve 3. `total` siempre coincide con la longitud de `datos`. Las fechas
salen en UTC con `Z`, y `reservaId` representa la columna SQL `id`.

Un viaje existente sin reservas, o un filtro sin coincidencias, responde 200
con `total: 0` y `datos: []`. Un viaje ajeno produce 403, un viaje inexistente
404 `VIAJE_NO_ENCONTRADO`, y una dependencia caída o inválida 503. En esos casos
no se ejecuta la consulta de reservas. Entrada inválida produce 400 y un token
ausente o inválido 401. Un fallo de la base propia produce 500 `ERROR_INTERNO`,
con mensaje genérico y sin exponer SQL, parámetros o nombres de pasajeros.

La ruta no escribe datos ni informa ocupación. Un viaje CANCELADO no excluye
sus reservas de esta consulta: la exclusión de viajes cancelados corresponde
a las estadísticas por conductor o vehículo. Swagger documenta las respuestas
400 y el formato de error del servicio, sin anunciar un 422 automático.

Prueba reproducible sin secretos reales ni servicios activos:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.verificar_reservas_viaje
$LASTEXITCODE
```

Se espera `Ran 18 tests`, `OK` y código 0. Se usan repositorio simulado, objetos
ORM de ejemplo, JWT efímero y Viajes en memoria. También se comprueba que el
SELECT generado para SQL Server está parametrizado y solo accede a reservas.
Las 103 pruebas anteriores pasaron con el nuevo contrato público de una ruta
GET protegida.

La comprobación adicional con SQL Server real leyó el seed de `unirride_reservas`
mediante el endpoint completo, con JWT y Viajes aislados. Resultados:

| Consulta | Estado HTTP | Total |
| --- | --- | --- |
| Viaje 305, sin filtro | 200 | 3 |
| Viaje 305, CONFIRMADA | 200 | 2 |
| Viaje 305, CANCELADA | 200 | 1 |
| Viaje 305, PENDIENTE | 200 | 0 |
| Viaje 308, sin reservas | 200 | 0 |
| Viaje 309, ajeno | 403 | Sin consulta SQL |
| Viaje inexistente | 404 | Sin consulta SQL |

Esta comprobación solo hizo lecturas; no insertó, modificó ni borró reservas.

### Uso manual cuando el equipo acuerde JWT_SECRET

El responsable indicó continuar con pruebas aisladas porque el secreto común
aún no está acordado. La ruta aparecerá en [Swagger de Reservas](http://localhost:8084/docs),
pero sus peticiones autenticadas reales necesitarán ese valor privado tanto en
Reservas como en Viajes. Configúralo en `.env` y reinicia los procesos cuando
esté disponible. `SERVICE_API_KEY` no se utiliza en esta consulta GET.

Con Viajes y SQL Server en ejecución, inicia Reservas desde la carpeta correcta:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m app.main
```

En otra terminal, después de configurar el secreto compartido:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
$token = .\.venv\Scripts\python.exe -m scripts.generar_jwt_mock --conductor-id 25
if ($LASTEXITCODE -ne 0) { throw 'Revisa JWT_SECRET.' }
$headers = @{Authorization = "Bearer $token"}
$resultado = Invoke-RestMethod 'http://localhost:8084/api/v1/reservas/viaje/305?estado=CONFIRMADA' -Headers $headers
$resultado.total
$resultado.datos
```

Se esperan total 2 y las reservas confirmadas del seed. Para el conductor 25,
el viaje 308 debe dar total 0; el 309 debe responder 403.

## Avance del plan

Al cerrar esta fase quedan implementadas 9 de las 18 fases previstas. Las fases
tienen alcances distintos; el trabajo pendiente se concentra en las estadísticas
y en validar la integración con los servicios reales.

| Fases pendientes | Trabajo |
| --- | --- |
| 10 | Detalle de una reserva |
| 11–13 | Estadísticas por viaje, conductor y vehículo |
| 14 | Informar ocupación a Viajes sin hacer fallar una consulta válida |
| 15–16 | Consolidar pruebas con pytest y colección Postman |
| 17 | Integración real con Viajes y Vehículos |
| 18 | Documentación final de instalación y uso |

Quedan nueve fases y cuatro endpoints de los cinco previstos. La infraestructura
de SQL, migraciones, seed, errores, trazabilidad, JWT, mocks y clientes HTTP ya
está preparada. La integración final depende también de las APIs de los compañeros
y de los secretos compartidos. La siguiente fase será la 10, después de la
comprobación del responsable.

## Archivos del proyecto por fases

- `app/main.py`: factoría FastAPI y arranque con puerto desde Settings.
- `app/controllers/reserva_controller.py`: GET de reservas por viaje.
- `app/services/reserva_service.py`: autorización y orquestación de la consulta.
- `app/repositories/reserva_repository.py`: SELECT propio por viaje y estado.
- `app/schemas/reserva_schema.py`: respuestas de reservas, con UTC y camelCase.
- `scripts/verificar_reservas_viaje.py`: comprobaciones de la fase 9.
- `app/clients/http_client.py`: transporte, timeout, reintentos y errores externos.
- `app/clients/viajes_client.py`: consultas paginadas y PUT interno preparado.
- `app/clients/vehiculos_client.py`: consulta y validación defensiva del vehículo.
- `app/schemas/integracion_schema.py`: contrato compartido por clientes y mocks.
- `scripts/verificar_clientes.py`: comprobaciones HTTP de la fase 8.
- `app/security/jwt_service.py`: validación HS256, dependencia Bearer y dueño.
- `app/config/settings.py`: configuración SQL y configuración JWT separadas.
- `scripts/verificar_jwt.py`: comprobaciones aisladas de autenticación y permisos.
- `scripts/verificar_configuracion_jwt.py`: presencia del secreto sin imprimirlo.
- `mocks/common.py`: arranque por URL, llave interna y validación de períodos.
- `mocks/schemas.py`: objetos del contrato para los mocks.
- `mocks/data.py`: viajes y vehículos de ejemplo independientes por instancia.
- `mocks/viajes_mock.py` y `mocks/vehiculos_mock.py`: aplicaciones locales.
- `scripts/verificar_mocks.py`: comprobaciones aisladas de la fase 7.
- `scripts/generar_jwt_mock.py`: utilidad local para probar solicitudes con JWT.
- `app/schemas/error_schema.py`: códigos y formato público de los errores.
- `app/exceptions/exceptions.py`: excepciones controladas del servicio.
- `app/exceptions/handlers.py`: traducción de excepciones a respuestas HTTP.
- `app/middleware/correlation_id.py`: UUID por solicitud y contexto aislado.
- `app/config/logging_config.py`: logs UTC con identificador de correlación.
- `scripts/verificar_http.py`: comprobaciones HTTP aisladas de esta fase.
- `app/config/database.py`: URL, engine y sesiones SQLAlchemy.
- `scripts/preparar_base_datos.py`: preparación administrativa idempotente.
- `scripts/verificar_conexion.py`: comprobación real con la cuenta SQL.
- `app/models/base.py` y `app/models/reserva.py`: metadatos y persistencia.
- `alembic.ini`, `alembic/env.py` y `alembic/script.py.mako`: entorno de migraciones.
- `alembic/versions/0001_crear_reservas.py`: primera migración.
- `scripts/verificar_estructura.py`: inspección de los catálogos de SQL Server.
- `scripts/seed_reservas.py`: carga repetible de los tres ejemplos.
- `scripts/verificar_seed_ssms.sql`: consultas de comprobación para SSMS.
- `.env.example`, `.gitignore`, `requirements.txt` y este README.

El primer endpoint de Reservas está implementado y verificado. Se continúa con
pruebas aisladas mientras se acuerdan los secretos reales. La fase 10 incorporará
`GET /api/v1/reservas/{reservaId}`; se espera la confirmación del responsable
antes de avanzar.

## Referencias técnicas

- [SQL Server y pyodbc con SQLAlchemy](https://docs.sqlalchemy.org/en/20/dialects/mssql.html#pyodbc)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Microsoft: modo de autenticación](https://learn.microsoft.com/en-us/sql/database-engine/configure-windows/change-server-authentication-mode)
- [PyJWT: validación y algoritmos permitidos](https://pyjwt.readthedocs.io/en/stable/api.html#jwt.decode)
- [PyJWT: claims y expiración](https://pyjwt.readthedocs.io/en/stable/usage.html)
- [HTTPX: timeouts](https://www.python-httpx.org/advanced/timeouts/)
- [HTTPX: transportes y reintentos](https://www.python-httpx.org/advanced/transports/)
