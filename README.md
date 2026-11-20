# UniRide

Portal del conductor con Usuarios, Vehículos, Viajes, Reservas y Estadísticas, API Gateway y frontend React. Cada microservicio conserva su propia base de datos; las llamadas entre equipos utilizan HTTP por Hamachi.

## Distribución del equipo

| Componente | Equipo | IP de Hamachi | Puerto | Motor |
| --- | --- | --- | ---: | --- |
| Usuarios | Arias | 25.32.113.17 | 8081 | SQL Server |
| Vehículos | LAPTOP | 25.0.88.33 | 8082 | PostgreSQL |
| Viajes | Andres | 25.33.226.75 | 8083 | PostgreSQL |
| Reservas | Apache | 25.1.20.39 | 8084 | SQL Server |
| Gateway | Arias | 25.32.113.17 | 8080 | Ninguno |
| Frontend | Arias o cada integrante | 25.32.113.17 si lo aloja Arias | 3000 | Ninguno |

Las direcciones se mantienen en `config/hamachi.json`. Si el Gateway cambia de equipo, cambia su `host` en ese archivo y vuelve a ejecutar el configurador para Gateway y Frontend. Estar en Hamachi no inicia las APIs: cada responsable debe arrancar su base y su servicio. Mantén los equipos despiertos y permite los puertos de sus APIs en el firewall únicamente para los integrantes de la red.

## Claves compartidas para la práctica

Actualiza tu copia con `git pull` y ejecuta los comandos desde la raíz de UNIRIDE. El configurador mezcla las variables de red con el `.env` del servicio y conserva todas las variables `DB_*`; crea una copia `.env.backup-*` si modifica un archivo existente. Si es tu primera instalación, crea `.env` desde el ejemplo y debes completar la conexión a tu propia base de datos.

Los valores de `JWT_SECRET` y `SERVICE_API_KEY` están publicados en [`config/claves-practica.env`](config/claves-practica.env), por solicitud del equipo para esta práctica. Son el mismo par ya acordado: el configurador los usa por defecto, aunque haya un archivo privado antiguo `config/.env.equipo` con otros valores. `JWT_SECRET` se aplica a los cuatro microservicios y `SERVICE_API_KEY` solo a Viajes y Reservas. También están incluidos en los `.env.example` correspondientes.

Estas claves son públicas y permiten firmar tokens de esta práctica. Su uso queda limitado al entorno académico. Las contraseñas de SQL Server/PostgreSQL y los tokens de sesión permanecen locales; el configurador conserva las variables `DB_*`.

Después de `git pull`, cada responsable ejecuta el configurador de su servicio y reinicia su API. El comando `Iniciar-Servicio.ps1` también aplica la configuración antes de arrancar, de modo que todos usan el mismo par publicado. Si arrancas directamente con Python, npm o Docker, ejecuta primero el configurador.

```powershell
# Cada responsable ejecuta SOLO el comando de su servicio.
.\scripts\Configurar-Hamachi.ps1 -Servicio Usuarios
.\scripts\Configurar-Hamachi.ps1 -Servicio Vehiculos
.\scripts\Configurar-Hamachi.ps1 -Servicio Viajes
.\scripts\Configurar-Hamachi.ps1 -Servicio Reservas

# En el equipo que ejecuta Gateway y en el que ejecuta el frontend:
.\scripts\Configurar-Hamachi.ps1 -Servicio Gateway
.\scripts\Configurar-Hamachi.ps1 -Servicio Frontend
```

Para usar deliberadamente otro par de claves, agrega `-ClavesRuta 'C:\ruta\claves-compartidas.env'`; todos los servicios deben usar ese mismo archivo. `-GenerarClaves` conserva la opción de crear un par privado aparte, sin cambiar el archivo público. Para una instalación completa en un único equipo, usa `-Servicio Todos -Local`; las URLs se cambian a `127.0.0.1`. El configurador no crea bases de datos ni ejecuta migraciones.

## Bases de datos y arranque

Requisitos: Node.js 26 para el frontend y sus pruebas, Python 3.12 o posterior para las APIs Python, SQL Server y ODBC Driver 18 para Usuarios/Reservas. PostgreSQL puede ejecutarse directamente o con los Compose existentes. SSMS y pgAdmin son clientes: los motores deben estar funcionando aunque esos programas estén cerrados.

Inicializa las bases y aplica las migraciones de cada servicio según su README. Conserva el puerto SQL real de tu equipo: no lo reemplaces automáticamente por 1433 ni por una IP de Hamachi. Los demás equipos consumen tu API, no tu base de datos.

Abre **una terminal por proceso**. Agrega `-Instalar` la primera vez para crear el entorno Python/instalar sus dependencias, o ejecutar `npm ci` en servicios Node. Los comandos no aplican migraciones ni alteran el firewall.

```powershell
.\scripts\Iniciar-Servicio.ps1 -Servicio Usuarios -Instalar
.\scripts\Iniciar-Servicio.ps1 -Servicio Viajes -Instalar
.\scripts\Iniciar-Servicio.ps1 -Servicio Reservas -Instalar
.\scripts\Iniciar-Servicio.ps1 -Servicio Gateway -Instalar
.\scripts\Iniciar-Servicio.ps1 -Servicio Frontend -Instalar
```

Vehículos puede iniciarse con su PostgreSQL y API en Docker:

```powershell
cd ms-vehiculos
docker compose up --build -d
```

O, con PostgreSQL ya iniciado, desde la raíz:

```powershell
.\scripts\Iniciar-Servicio.ps1 -Servicio Vehiculos -Instalar
```

El Compose de Viajes inicia únicamente PostgreSQL. Si lo utilizan, ejecuten `docker compose up -d` en `ms-viajes`, esperen a que su base esté lista y después inicien la API Node. Si ambas bases PostgreSQL están en un mismo equipo, sus puertos publicados deben ser distintos; Vehículos utiliza 5434 y Viajes utiliza `DB_PORT` de su `.env`.

Todas las APIs escuchan por defecto en `0.0.0.0`, configurable mediante `SERVER_HOST`. El frontend acepta conexiones de red con `FRONTEND_HOST=0.0.0.0`; Arias puede abrir `http://localhost:3000` y sus compañeros `http://25.32.113.17:3000`. También pueden ejecutar su propio frontend local apuntando al Gateway de Arias. El configurador utiliza `GATEWAY_URL=http://25.32.113.17:8080`, accesible tanto desde Arias como desde los otros equipos por Hamachi. Si frontend y Gateway se ejecutan en Arias, `http://127.0.0.1:8080` también sirve como destino local manual. El proxy del frontend mantiene el acceso a la API a través del Gateway; `JWT_SECRET` y `SERVICE_API_KEY` nunca se incluyen en Vite.

Reinicia las APIs después de cambiar `.env`. Con Docker, recrea los contenedores (`docker compose up --build -d`); un simple reinicio puede conservar la configuración anterior. No borres volúmenes para cambiar direcciones o claves.

## Comprobación de la integración

```powershell
.\scripts\Comprobar-Conexion.ps1
```

El diagnóstico distingue falta de conexión TCP de una API con base/dependencias no preparadas. `/health` comprueba el proceso; `/health/ready` devuelve 200 cuando está preparado y 503 si falla SQL/PostgreSQL. En Gateway, readiness consulta las cuatro APIs en paralelo y muestra qué dependencia no está lista. Es un diagnóstico sin datos personales ni mensajes del proveedor de base de datos.

Con todos los servicios listos, entra al frontend y registra una cuenta, inicia sesión, registra un vehículo y publica un viaje. Reservas y estadísticas utilizan los identificadores reales creados por ese flujo, no IDs escritos manualmente ni tokens de los mocks.

Existe además una comprobación funcional automatizada **que escribe datos reales de prueba**:

```powershell
node scripts/probar-flujo.mjs --gateway http://25.32.113.17:8080 --crear-datos-de-prueba
```

Registra una cuenta de ejemplo, inicia sesión, crea un vehículo y un viaje, edita con versión, consulta reservas y las tres estadísticas, finaliza el viaje y desactiva el vehículo. No imprime tokens ni contraseñas. Los registros de prueba permanecen en el historial; si falla a mitad del recorrido, revisa los IDs creados antes de repetirlo.

Un viaje recién creado puede tener cero reservas: la API de Reservas es de consulta. Para poblar ejemplos en un viaje real destinado a pruebas, ejecuta en Reservas `python -m scripts.seed_reservas --viaje-id ID_REAL`. Ese comando escribe únicamente en la base de Reservas. El valor predeterminado 305 conserva los ejemplos antiguos; no implica que exista ese viaje en la base de Viajes del equipo.

## Pruebas aisladas

```powershell
# Desde la raíz, sin bases reales:
.\tests\configuracion.ps1

# Dentro de cada API Python, con requirements-dev.txt instalado:
.\.venv\Scripts\python.exe -m pytest -q

# Dentro de api-gateway, ms-viajes y frontend-uniride:
npm.cmd test

# Dentro de frontend-uniride:
npm.cmd run build
```

Las suites de SQL real son optativas y se mantienen deshabilitadas por defecto. Las pruebas de proxy y servicios usan repositorios/proveedores simulados; la disponibilidad de los equipos de Hamachi se comprueba con el diagnóstico y la prueba funcional real.

## Contratos entre servicios

Usuarios firma JWT HS256 con `sub` textual del conductor e `iat`/`exp` enteros. Vehículos y Viajes verifican propietario; las lecturas y modificaciones de Viajes quedan limitadas al conductor del token. Reservas valida sus dependencias y consulta solo viajes propios. La correlación utiliza UUID y se propaga por Gateway y servicios. Los DTO públicos usan camelCase.

Viajes consume Vehículos directamente; Reservas consume Viajes y Vehículos directamente. La ocupación se sincroniza mediante un total absoluto e idempotente y `X-Service-Key`, sin JWT. Gateway bloquea la ruta interna `/api/v1/viajes/{id}/ocupacion`. No añadas `SERVICE_API_KEY` al navegador ni expongas el servidor de desarrollo Vite a Internet.

## Prueba funcional con servicios reales

Después del diagnóstico, pueden ejecutar el recorrido completo contra su Gateway:

```powershell
node .\scripts\probar-flujo.mjs --gateway http://25.32.113.17:8080 --crear-datos-de-prueba
```

Esta prueba escribe datos: registra una cuenta ficticia, inicia sesión, registra un vehículo, publica y edita un viaje, consulta reservas y estadísticas, finaliza el viaje y desactiva el vehículo. La cuenta y los registros de historial permanecen como datos de prueba. No imprime ni guarda la contraseña o el JWT. Si falla, muestra los identificadores que ya se crearon para poder revisarlos.

Reservas es un módulo de consulta y no crea reservas desde el frontend. Para mostrar pasajeros en un viaje real, el responsable de Reservas puede ejecutar su seed con el ID de un viaje que haya creado el equipo. El ID 72 es solo un ejemplo; reemplázalo por el real:

```powershell
cd ms-reservas-estadisticas
.\.venv\Scripts\python.exe -m scripts.seed_reservas --viaje-id 72
```

El seed escribe tres ejemplos únicamente en `unirride_reservas` y conserva ejemplos ya existentes. No se ejecuta como parte del arranque ni de las pruebas aisladas. No es necesario sembrar datos para que una consulta sin reservas responda correctamente con ceros.

## Pruebas aisladas del repositorio

Ejecuta cada comando desde la carpeta indicada:

| Carpeta | Comando |
| --- | --- |
| `ms-usuarios-auth` | `.\.venv\Scripts\python.exe -m pytest -q` |
| `ms-vehiculos` | `.\.venv\Scripts\python.exe -m pytest -q` |
| `ms-reservas-estadisticas` | `.\.venv\Scripts\python.exe -m pytest -q` |
| `ms-viajes` | `npm.cmd test` |
| `api-gateway` | `npm.cmd test` |
| `frontend-uniride` | `npm.cmd test` y `npm.cmd run build` |

Las suites Python requieren instalar `requirements-dev.txt` en su entorno. Las lecturas SQL reales siguen siendo opcionales y se omiten por defecto. Desde la raíz, `powershell.exe -File .\tests\configuracion.ps1` verifica el configurador con archivos temporales y claves ficticias, sin modificar las configuraciones reales.

Las pruebas aisladas verifican los contratos, el proxy y la configuración usando repositorios o proveedores simulados. La disponibilidad de los equipos Hamachi, sus bases y las credenciales privadas se comprueba con el diagnóstico y el recorrido real cuando estén encendidos.
