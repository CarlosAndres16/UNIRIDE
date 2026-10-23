# UniRide — Reservas y Estadísticas

Responsable: **Juan Alejandro Apache Moreno**. Microservicio
`ms-reservas-estadisticas`, versión **1.0.0**, puerto **8084**.
Fuente de verdad: «UniRide – Contrato Técnico Unificado».
Se utiliza **Python 3.13.2**, instalado en este equipo, por indicación del responsable.

## Estado de la entrega

Implementadas las consultas de reservas, las tres estadísticas, la actualización
interna de ocupación, los mocks, los clientes HTTP, la colección Postman y esta guía.
Las reservas se cargan mediante seed y son de solo lectura en la API.
Las estadísticas se calculan al consultar y no se guardan en tablas.

La integración con los servicios reales queda preparada mediante configuración.
Para cerrarla faltan las URLs accesibles de Viajes y Vehículos, un JWT emitido por
Usuarios y los valores privados acordados de `JWT_SECRET` y `SERVICE_API_KEY`.
El Gateway corresponde al equipo y debe enrutar los dos prefijos de este servicio.

Las pruebas finales están implementadas en `tests/` y ejecutadas con pytest:
**232 pruebas aprobadas y 261 subcasos aprobados**, incluyendo tres comprobaciones
de lectura con SQL Server real. Los verificadores anteriores se adaptaron al
contrato de cinco endpoints y forman parte de la suite de regresión. Los clientes
HTTP se comprueban con dependencias simuladas y credenciales aleatorias temporales;
la integración con los servicios reales del equipo sigue pendiente.
Consulta `docs/PRUEBAS_FINALES.md` para repetirlas y revisar su alcance.

## Requisitos y entorno

- Windows con Python **3.13** de 64 bits; versión local utilizada: **3.13.2**.
- SQL Server / SQL Express con TCP habilitado y autenticación SQL.
- Microsoft ODBC Driver 18 for SQL Server de 64 bits.
- Dependencias fijadas en `requirements.txt`: FastAPI, Uvicorn, SQLAlchemy 2,
  pyodbc, Alembic, Pydantic 2, pydantic-settings, httpx y PyJWT.

El proyecto local está en `X:\Proyecto Uniride\ms-reservas-estadisticas`.
El entorno y la base ya están preparados en este equipo. No es necesario
recrearlos para utilizar los archivos actualizados.

En una copia nueva, desde PowerShell:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item -LiteralPath '.env.example' -Destination '.env'
```

La copia del ejemplo corresponde únicamente a una instalación nueva que aún no
tenga `.env`. Conserva el `.env` actual: contiene la configuración SQL privada.
Los comandos usan el intérprete directamente y no requieren activar el entorno.

## Configuración privada

`app/config/settings.py` lee el entorno y el `.env` de la carpeta del proyecto.

| Variable | Uso / valor local |
| --- | --- |
| `SERVER_PORT` | `8084` |
| `DB_HOST` | `DESKTOP-LLK6D0L\SQLEXPRESS` |
| `DB_PORT` | **29178** en esta instancia; el ejemplo genérico usa 1433 |
| `DB_NAME` | `unirride_reservas` |
| `DB_USER` | `unirride_reservas_app` |
| `DB_PASSWORD` | Contraseña SQL privada; ya configurada localmente |
| `DB_DRIVER` | `ODBC Driver 18 for SQL Server` |
| `JWT_SECRET` | Mismo secreto HS256 privado en los cuatro servicios; pendiente de acuerdo |
| `SERVICE_API_KEY` | Misma llave privada en Reservas y Viajes; pendiente de acuerdo |
| `VIAJES_SERVICE_URL` | `http://localhost:8083` para el mock o la URL base real |
| `VEHICULOS_SERVICE_URL` | `http://localhost:8082` para el mock o la URL base real |
| `HTTP_TIMEOUT_MS` | `3000` por intento |
| `HTTP_MAX_RETRIES` | `1`; admite 0 para desactivar el reintento |

Las URLs son bases de servicio, sin `/api/v1`, credenciales, parámetros ni
fragmentos. `.env` está excluido por `.gitignore`. No copies secretos al chat,
al repositorio, a `.env.example` ni a las exportaciones de Postman.

La autenticación se carga al usar un endpoint protegido. Swagger puede abrirse
sin `JWT_SECRET`, pero las operaciones requieren un JWT validable. Un Bearer
presente con configuración JWT ausente produce un 500 de configuración; un token
ausente o inválido produce 401. Los mocks requieren el secreto para sus GET.

## Base de datos y seed

El servicio es dueño únicamente de `unirride_reservas`. No lee las bases de
Usuarios, Vehículos ni Viajes. Los identificadores externos se guardan como
enteros, sin claves foráneas hacia otras bases.

La conexión usa `URL.create`, `mssql+pyodbc`, cifrado y
`TrustServerCertificate=yes` para desarrollo local. Crear la aplicación no abre
una conexión SQL. Cada petición usa su propia sesión; el trabajo SQL síncrono
se realiza fuera del event loop.

En una instalación nueva, configura primero `.env`. Para preparar la base y la
cuenta con un usuario Windows administrador de la instancia:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m scripts.preparar_base_datos
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_reservas
```

El preparador conserva la base, los usuarios y las contraseñas existentes.
No habilita el modo mixto ni reinicia SQL Server; eso ya se hizo con autorización
en este equipo. La cuenta de aplicación tiene permisos dentro de su propia base,
sin roles de servidor. Alembic crea `dbo.reservas` y la tabla técnica
`dbo.alembic_version`; no se utiliza `create_all` al arrancar la API.

| Columna SQL | Tipo / regla |
| --- | --- |
| `id` | `INT IDENTITY`, clave primaria |
| `viaje_id` | `INT`, obligatorio y positivo |
| `pasajero_nombre` | `NVARCHAR(150)`, obligatorio y no vacío |
| `cupos_reservados` | `INT`, mínimo 1 |
| `estado` | `PENDIENTE`, `CONFIRMADA` o `CANCELADA` |
| `fecha_reserva` | `DATETIME2(6)`, UTC |

Existe un índice sobre viaje y estado. El modelo convierte fechas con zona a UTC
y rechaza fechas Python sin zona. La API serializa timestamps en ISO 8601 con
`Z`. `pasajeroNombre` es un dato de la reserva; no representa una cuenta de pasajero.

El seed es repetible y conserva filas existentes. Ya se cargaron estos ejemplos:

| Reserva local | Viaje | Pasajero | Cupos | Estado |
| --- | --- | --- | --- | --- |
| 1 | 305 | Laura Gómez | 1 | CONFIRMADA |
| 2 | 305 | David Ruiz | 1 | CONFIRMADA |
| 3 | 305 | Carlos Pérez | 1 | CANCELADA |

Los IDs son asignados por SQL Server y pueden diferir en otra instalación.
El seed no borra reservas ni reinicia identidades.

## Arranque en PowerShell

Inicia cada proceso en una terminal distinta, desde la carpeta que contiene
`app` y `mocks`. Si ya están en ejecución, conserva esos procesos; tras cambiar
`.env`, detén y vuelve a iniciar el proceso correspondiente.

Vehículos mock:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m mocks.vehiculos_mock
```

Viajes mock:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m mocks.viajes_mock
```

Reservas y Estadísticas:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m app.main
```

| Servicio | Swagger |
| --- | --- |
| Reservas y Estadísticas | <http://localhost:8084/docs> |
| Viajes mock | <http://localhost:8083/docs> |
| Vehículos mock | <http://localhost:8082/docs> |

La API principal usa recarga automática. Los mocks utilizan un solo proceso y
guardan su estado en memoria: al reiniciarlos se restauran los ejemplos. Sus
puertos se toman de las respectivas URLs; `SERVER_PORT` solo configura Reservas.
La ruta `/` no está definida y responde 404.

## API versión 1

Todos los endpoints requieren `Authorization: Bearer <JWT>`.

| Método | Ruta | Filtros opcionales |
| --- | --- | --- |
| GET | `/api/v1/reservas/viaje/{viajeId}` | `estado=PENDIENTE`, `CONFIRMADA` o `CANCELADA` |
| GET | `/api/v1/reservas/{reservaId}` | — |
| GET | `/api/v1/estadisticas/viaje/{viajeId}` | — |
| GET | `/api/v1/estadisticas/conductor/{conductorId}` | `desde`, `hasta` |
| GET | `/api/v1/estadisticas/vehiculo/{vehiculoId}` | `desde`, `hasta` |

`desde` y `hasta` usan exactamente `YYYY-MM-DD`, son independientes y filtran
`fechaSalida` con límites inclusivos. Si ambos llegan, `desde <= hasta`.
Sin filtros, `periodo` es `null`; con un solo límite, el otro campo es `null`.

El JWT usa HS256 y los claims `sub`, `iat`, `exp`. `sub` identifica al conductor
como texto decimal positivo. No hay roles ni llamadas a Usuarios para validarlo.
Para consultar un conductor, el ID del path debe coincidir con `sub`. En los
demás recursos se comprueba el dueño obtenido de Viajes o Vehículos antes de
devolver datos. Para el detalle se lee primero la reserva propia para obtener
su `viajeId`, sin entregar datos hasta autorizar el viaje.

Las respuestas mantienen los campos camelCase del contrato. El detalle devuelve
un objeto directo; el listado devuelve `viajeId`, `total`, `datos`. Un viaje
existente sin reservas responde 200 con `total=0` y `datos=[]`.

## Cálculos y ocupación

- `pasajerosConfirmados`: suma de `cuposReservados` de reservas `CONFIRMADA`.
- `cuposOfrecidos`: capacidad del viaje recibida de Viajes.
- `cuposDisponibles`: máximo entre `cuposOfrecidos - pasajerosConfirmados` y 0.
- Porcentaje: pasajeros confirmados / cupos ofrecidos × 100, redondeo a dos
  decimales y límite entre 0 y 100 conforme a las reglas comunes del contrato.
  Capacidad cero devuelve 0 y registra el caso; una capacidad cero recibida por
  HTTP es un DTO inválido porque Viajes exige capacidad de 1 a 8.
- Los agregados incluyen `ACTIVO` y `FINALIZADO`, excluyen `CANCELADO`, recorren
  todas las páginas de Viajes con `estado=TODOS` y `tamano=50` y cuentan las
  reservas únicamente de esos viajes. Cero viajes devuelve contadores y promedio 0.
- `vehiculosUtilizados` cuenta IDs distintos de los viajes incluidos. La
  capacidad acumulada proviene de cada viaje, no de la ficha actual del vehículo.

**Decisión local documentada:** el contrato no especifica cómo ponderar
`porcentajeOcupacionPromedio`. Se utiliza la ocupación ponderada por capacidad:
`SUM(pasajerosConfirmados) / SUM(capacidadViaje) * 100`, con las mismas reglas
de redondeo y límites. Conviene confirmar esta convención al integrar con el equipo.
Los contadores reales de pasajeros se conservan incluso si exceden la capacidad.

Las consultas agrupan las reservas en SQL por viaje y estado, dividiendo listas
de IDs en bloques de hasta 1000 para respetar el límite de parámetros de SQL Server.
No se almacena ningún resumen estadístico.

Después de una lectura autorizada, si un viaje `ACTIVO` muestra disponibilidad
distinta de la calculada, se informa directamente a Viajes:

```http
PUT /api/v1/viajes/{viajeId}/ocupacion
X-Service-Key: <SERVICE_API_KEY>
X-Correlation-Id: <mismo UUID>
Content-Type: application/json

{"cuposOcupados": 2}
```

Se envía el total confirmado completo, nunca un incremento ni un total limitado a
la capacidad. El filtro `estado` del listado no modifica este total. Si Viajes ya
muestra la disponibilidad correcta, no se emite un PUT. Los viajes finalizados o
cancelados no se actualizan. La llamada interna usa la llave de servicio y no el JWT.

El cliente realiza como máximo un reintento ante un fallo reintentable. Si el
informe falla, se registra el error con su UUID y se conserva la consulta válida.
La siguiente consulta vuelve a detectar la diferencia y permite reintentar.
En esta versión de lectura, los cambios realizados directamente en SQL se
detectan al consultar; no hay monitor de base de datos ni tarea periódica.

## Errores, HTTP y trazabilidad

`X-Correlation-Id` acepta un UUID; si falta, se genera uno. Se reenvía a las
dependencias y vuelve en el header de respuesta. Un valor inválido o duplicado
produce 400 con un UUID nuevo. Los errores de aplicación contienen exactamente
`timestamp`, `status`, `error`, `message`, `path`, `correlationId`; los 400 añaden
la lista `detalles`. Los timestamps son UTC. No se registran tokens, claves,
contraseñas, nombres de pasajeros ni cuerpos HTTP.

| Estado | Significado |
| --- | --- |
| 400 | Identificador, filtro, fecha o formato inválido |
| 401 | JWT ausente/inválido/vencido; autenticación interna rechazada por el proveedor |
| 403 | Recurso de otro conductor |
| 404 | Reserva, viaje o vehículo inexistente, con su código específico |
| 500 | Error interno, SQL o configuración obligatoria ausente |
| 503 | Dependencia inaccesible, timeout o respuesta técnicamente inválida |

Los GET a Viajes y Vehículos reenvían el JWT. Se conservan los errores de dominio
válidos 400/401/403/404 del proveedor. Las llamadas tienen timeout de tres segundos
por intento y como máximo un reintento en GET y en el PUT de ocupación. No se
siguen redirecciones ni se utiliza el proxy del entorno para reenviar credenciales.
Este servicio no genera 504. CORS y el timeout del Gateway pertenecen al Gateway.

**Vacío del contrato:** no hay código de dominio definido para rutas inexistentes
o métodos no permitidos. Esos 404/405 conservan provisionalmente la respuesta de
enrutamiento de FastAPI y también incluyen `X-Correlation-Id`.

## Postman e integración real

Importa ambos archivos en Postman y selecciona el entorno **UniRide - Local**:

- `postman/UniRide-Reservas-Estadisticas.postman_collection.json`
- `postman/UniRide-Local.postman_environment.json`

El entorno exportado no contiene tokens ni llaves. Configura `accessToken`
localmente con un JWT válido sin el prefijo `Bearer`, y la llave interna solo si
vas a utilizar la petición opcional de ocupación directa. La colección incluye
las cinco consultas y un grupo separado para las dependencias. No contiene
scripts de pruebas y no fue ejecutada en esta ampliación.

Los mocks incluyen el conductor 25, vehículo 12 y viaje 305; el vehículo 13 tiene
otro viaje y el vehículo 15 está inactivo y sin viajes. El conductor 26 permite
representar recursos ajenos y el 27 dispone de 51 viajes para paginación. Los
mocks no crean usuarios ni emiten JWT por una API.

Cuando estén disponibles los servicios reales:

1. Acuerda privadamente `JWT_SECRET` con Usuarios, Vehículos y Viajes, y
   `SERVICE_API_KEY` con Viajes.
2. Configura las URLs base reales en `.env`. Si utilizan los mismos puertos
   locales que los mocks, detén los mocks antes de arrancar los servicios reales.
3. Usa IDs existentes y un JWT emitido por Usuarios. Los IDs del seed y de los
   mocks no implican que esos recursos existan en las bases de tus compañeros.
4. Reinicia Reservas para cargar la configuración. No se requieren cambios en
   controllers, services ni repositories.
5. El Gateway debe reenviar `/api/v1/reservas/**` y `/api/v1/estadisticas/**`
   conservando JWT y UUID. El PUT de ocupación es directo y no debe publicarse
   en el Gateway.

La compatibilidad HTTP se describe en `docs/INTEGRACION.md`. Esta preparación no
equivale a haber integrado los servidores reales; esa etapa sigue pendiente.

## Pruebas finales

Instala las dependencias de desarrollo si aún no están disponibles:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Suite aislada, sin consultar SQL Server:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Suite completa con lecturas de SQL Server local e informe JUnit:

```powershell
.\.venv\Scripts\python.exe -m pytest --sql-server -q --junitxml=reports/pruebas-finales.xml
```

No es necesario arrancar los tres servidores para estas pruebas: las aplicaciones
HTTP se ejecutan dentro del proceso de pruebas. `--sql-server` requiere SQL Server
disponible y el seed existente del viaje 305; no crea ni modifica reservas. Los
JWT y llaves internos de las pruebas son temporales y no cambian `.env`.

## Problemas habituales

**`ModuleNotFoundError: No module named 'app'`:** ejecuta los comandos desde
`X:\Proyecto Uniride\ms-reservas-estadisticas`, usando
`.\.venv\Scripts\python.exe -m app.main`. Ejecutar `app/main.py` directamente o
`python -m app.main` desde `X:\Proyecto Uniride` causa el problema de importación.

**Swagger no abre:** inicia el servicio correspondiente en su terminal y revisa
la URL y el puerto configurados. Abrir Swagger no arranca el servidor. El error
de puerto ocupado indica que ya existe un proceso escuchando; evita iniciar una
segunda instancia en el mismo puerto.

**Swagger abre pero las consultas fallan:** 401 requiere revisar el JWT;
503 requiere disponibilidad y contrato HTTP de las dependencias; 500 requiere
revisar configuración o SQL con el UUID del error. No compartas `.env` ni el token.

**SQL Express cambió de puerto:** esta instancia utiliza TCP 29178; si la
configuración de SQL cambia, ajusta `DB_PORT` al puerto real. SSMS puede conectar
por otro mecanismo aunque la conexión TCP de Python no esté disponible.

## Organización

```text
app/
  clients/       HTTP a Viajes y Vehículos
  config/        Variables, SQLAlchemy y logging
  controllers/   Las cinco rutas GET
  exceptions/    Errores del contrato y manejadores
  middleware/    UUID de correlación
  models/        Reserva, enum y fecha UTC
  repositories/  Lecturas SQL y agregación
  schemas/       DTO públicos y externos
  security/      JWT e identificación del conductor
  services/      Reservas, estadísticas y ocupación
alembic/         Migraciones SQL Server
docs/            Acuerdo HTTP e historial de la fase 9
mocks/           Simuladores locales reemplazables por URLs
postman/         Colección y entorno sin secretos
scripts/         Preparación SQL, seed y verificadores históricos
tests/           Aceptación, regresión, repositorio y SQL real optativo
reports/         Informes JUnit de las ejecuciones
```

La carpeta hermana `X:\Proyecto Uniride\entregas` conserva las guías de las fases
previas y la entrega final con el contenido completo de los archivos implementados.
