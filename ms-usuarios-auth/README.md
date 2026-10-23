# ms-usuarios-auth · UniRide

Backend de Usuarios y Autenticación para conductores. Registra conductores, verifica contraseñas, emite JWT y permite consultar y actualizar el recurso propio. Implementa los cinco endpoints del Contrato Técnico Unificado.

Se entregan juntas las fases de implementación, la suite pytest y la colección Postman. Por solicitud del usuario **no se ejecutaron instalaciones, pruebas, comprobaciones de servicios, migraciones ni arranque**. La presencia del código de una fase no acredita que su infraestructura esté configurada o que sus pruebas hayan pasado. El estado se detalla en [docs/estado_fases.md](docs/estado_fases.md).

El archivo `.env` privado ya quedó preparado localmente con las credenciales proporcionadas y un `JWT_SECRET` aleatorio. No se muestran esos valores ni se incluyen en los ejemplos. Queda pendiente acordar ese secreto con los demás servicios por un canal privado.

## Requisitos en Windows

- Python 3.12 disponible mediante el lanzador `py` o mediante `python` en el PATH.
- Microsoft SQL Server accesible por TCP, normalmente `localhost:1433`; habilitar TCP/IP y un inicio de sesión SQL con los permisos necesarios.
- SQL Server Management Studio (SSMS) para administrar el servidor. SSMS es el cliente; instalarlo no instala el motor SQL Server.
- Microsoft ODBC Driver 18 for SQL Server de 64 bits, compatible con la arquitectura de Python.
- Windows PowerShell y acceso al registro de paquetes para instalar dependencias.

El servicio usa FastAPI, Uvicorn, Pydantic v2, pydantic-settings, SQLAlchemy 2.x, pyodbc, Alembic, PyJWT y argon2-cffi. pytest y httpx se utilizan para pruebas; httpx no interviene en la comunicación del servicio.

## Preparación con PowerShell

Abrir PowerShell en esta carpeta. Todos los comandos siguientes son instrucciones para ejecutar cuando se quiera preparar el entorno; no se han ejecutado durante la entrega.

```powershell
Set-Location 'C:\Users\juadi\OneDrive\Desktop\Uni\Distribuidos\Auth\ms-usuarios-auth'
.\scripts\setup.ps1
```

`setup.ps1` prepara el entorno virtual, instala dependencias y guía la configuración local; también crea la base y aplica Alembic. Revisar el script antes de ejecutarlo para conocer sus pasos y solicitudes de credenciales. La alternativa manual permite separar cada operación:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item -LiteralPath .env.example -Destination .env
```

Estos comandos crean y activan el entorno virtual, instalan las dependencias y preparan el archivo de configuración. El comando `Copy-Item` es solo para la primera configuración; conservar un `.env` ya completado. Si la política de PowerShell impide activar el entorno, puede usarse directamente `.\.venv\Scripts\python.exe` en lugar de `python`.

Para incluir dependencias de pruebas, usar `.\scripts\setup.ps1 -IncluirPruebas`, o instalar manualmente `python -m pip install -r requirements-dev.txt` después de activar el entorno. Estos comandos preparan dependencias; no ejecutan pytest. El script conserva un `.env` existente, genera el secreto si está vacío y solicita la contraseña SQL de forma privada solo si falta.

## Variables de entorno

Si se prepara otra copia del proyecto, completar `.env` localmente. `DB_PASSWORD` y `JWT_SECRET` se dejan vacíos en `.env.example` deliberadamente. El arranque con configuración incompleta debe fallar, en vez de utilizar secretos predeterminados.

| Variable | Uso |
| --- | --- |
| `SERVER_PORT` | Puerto HTTP local; `8081`. |
| `DB_HOST` | Host SQL Server; normalmente `localhost`. |
| `DB_PORT` | Puerto TCP SQL Server; normalmente `1433`. |
| `DB_NAME` | Base propietaria de este servicio: `unirride_usuarios`. |
| `DB_USER` | Inicio de sesión SQL configurado localmente. |
| `DB_PASSWORD` | Contraseña privada del inicio de sesión SQL. |
| `DB_DRIVER` | `ODBC Driver 18 for SQL Server`. |
| `JWT_SECRET` | Secreto privado compartido entre los cuatro microservicios; al menos 32 bytes UTF-8. |
| `JWT_EXPIRES_IN_SECONDS` | Vigencia del token; `3600` segundos por defecto. |

No copiar credenciales a código, capturas, documentación ni repositorio. `.gitignore` excluye `.env`, entornos virtuales y cachés. El secreto compartido debe acordarse por un canal privado entre los equipos: Usuarios firma; Vehículos, Viajes y Reservas verifican localmente con HS256. Para integración, todos deben usar el mismo valor; un secreto local generado automáticamente no coordina por sí solo los demás servicios.

La conexión `mssql+pyodbc` se construye desde las variables mediante SQLAlchemy; no hay cadena con credenciales incrustada. El certificado del servidor se acepta para el desarrollo local con `TrustServerCertificate=yes`. Esa configuración local no sustituye la configuración de certificados del entorno de despliegue.

## Base de datos y Alembic

```powershell
python -m scripts.create_database
python -m alembic upgrade head
```

El primer comando crea `unirride_usuarios` si no existe y requiere un inicio de sesión con permisos para crearla. El segundo aplica la migración que crea `dbo.conductores`. Si el usuario de la aplicación no tiene permiso para crear bases, un administrador puede crearla desde SSMS y después ejecutar Alembic con los permisos adecuados.

Datos iniciales opcionales de desarrollo:

```powershell
python -m scripts.seed --nombre 'Juan Apache' --correo 'juan@example.com' --telefono '3001234567'
```

El seed pide la contraseña sin mostrarla, solicita confirmación y utiliza el mismo `AuthService` y `PasswordService` que el registro. No acepta contraseñas por argumentos ni reemplaza un conductor existente.

La aplicación no crea tablas al arrancar y no utiliza `Base.metadata.create_all()` en producción. Las migraciones son el mecanismo versionado del esquema.

| Columna SQL Server | Tipo | Decisión |
| --- | --- | --- |
| `id` | `INT IDENTITY(1,1)` | Clave primaria. |
| `nombre` | `NVARCHAR(150)` | Nombre Unicode con un límite práctico. |
| `correo` | `NVARCHAR(254)` | Dirección normalizada a minúsculas y única. |
| `password_hash` | `NVARCHAR(255)` | Margen para el hash Argon2id codificado. |
| `telefono` | `NVARCHAR(30) NULL` | Admite prefijos y formato internacional; no se trata como número. |
| `activo` | `BIT` | Verdadero por defecto. |
| `fecha_creacion` | `DATETIME2(6)` | Instante de creación en UTC. |
| `fecha_actualizacion` | `DATETIME2(6)` | Instante UTC de la última actualización. |

Los tamaños son detalles de implementación, no nuevos campos funcionales. `DATETIME2` no conserva zona horaria: la aplicación escribe valores UTC sin `tzinfo`, y las respuestas de error serializan su timestamp con zona UTC. Los timestamps internos no forman parte del objeto público Conductor.

## Ejecución

```powershell
.\scripts\start.ps1
```

El script inicia Uvicorn usando `SERVER_PORT`. La URL local predeterminada es `http://localhost:8081`. Swagger UI está en `http://localhost:8081/docs` y el esquema de herramientas en `/openapi.json`. `/` no es un endpoint de negocio; solo están implementadas las cinco rutas contractuales. ReDoc está deshabilitado.

## API y autenticación

| Método | Ruta | JWT | Resultado |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/registro` | No | `201` Conductor. |
| POST | `/api/v1/auth/login` | No | `200` Token y conductorId. |
| GET | `/api/v1/auth/me` | Sí | `200` Conductor identificado por `sub`. |
| GET | `/api/v1/conductores/{conductorId}` | Sí | `200` Recurso propio. |
| PUT | `/api/v1/conductores/{conductorId}` | Sí | `200` Nombre y teléfono actualizados. |

Registro requiere `nombre`, `correo` y `password` de al menos ocho caracteres; `telefono` puede omitirse o ser `null`. El correo se normaliza también en login. Un duplicado devuelve `409 CORREO_YA_REGISTRADO`. El objeto Conductor contiene exactamente `conductorId`, `nombre`, `correo`, `telefono` y `activo`.

Login devuelve `accessToken`, `tokenType: "Bearer"`, `expiresIn` y `conductorId`. Los endpoints protegidos reciben `Authorization: Bearer <accessToken>`. El JWT utiliza HS256 y exclusivamente los claims `sub`, `iat` y `exp`; `sub` es el identificador del conductor como texto. No contiene roles. Firma inválida, expiración, claims requeridos ausentes o identidad inválida producen `401 NO_AUTENTICADO`.

GET y PUT verifican primero que el identificador del path coincida con el del JWT; un recurso ajeno devuelve `403 NO_AUTORIZADO`. Una identidad propia válida cuyo conductor no existe devuelve `404 CONDUCTOR_NO_ENCONTRADO`. PUT requiere `nombre`, admite `telefono` nullable y rechaza campos adicionales: no permite cambiar correo, contraseña, activo ni identificadores.

Se eligió **Argon2id mediante argon2-cffi** por ser una biblioteca especializada, con salt aleatoria y parámetros de costo administrados por el algoritmo. Además admite contraseñas Unicode largas sin la limitación de 72 bytes de bcrypt. La lógica se concentra en `PasswordService`, fuera de controladores y repositorios. Véase la [documentación oficial de argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/).

La conducta del login de una cuenta inactiva requiere acuerdo funcional del equipo. Se deja explícitamente pendiente: esta versión no añade un bloqueo silencioso. Un token ya emitido puede conservar validez hasta su expiración, conforme a la limitación contractual. No hay listas de revocación.

## Errores y correlación

Todos los endpoints aceptan `X-Correlation-Id` con un UUID. Si falta, se genera uno. Si se proporciona un UUID válido, se conserva literalmente en logs, header de respuesta y `ErrorResponse`. Un valor mal formado produce `400 FORMATO_INVALIDO` con un nuevo UUID válido para poder trazar el error.

```json
{
  "timestamp": "2026-10-22T12:00:00Z",
  "status": 404,
  "error": "CONDUCTOR_NO_ENCONTRADO",
  "message": "No existe un conductor con id 25.",
  "path": "/api/v1/conductores/25",
  "correlationId": "3e18f132-65dd-4e84-8b48-d5a69e71a850"
}
```

Los errores de entrada usan HTTP 400 en lugar del 422 predeterminado e incluyen `detalles` con `campo` y `problema`. No reflejan los valores recibidos. Login usa el mismo mensaje genérico para correo o contraseña incorrectos. Los errores 500 no devuelven detalles SQL, credenciales ni trazas. Los logs de acceso contienen método, ruta, estado y correlación; no registran cuerpos, contraseñas ni JWT.

## Pruebas preparadas

```powershell
python -m pytest -q
```

Este comando permite ejecutar opcionalmente la suite. No se ejecutó en esta entrega. Las pruebas HTTP utilizan una base SQLite efímera, `StaticPool`, `schema_translate_map` y reemplazos de dependencias; no leen el `.env` real ni acceden a SQL Server. `create_all()` se limita a esa base de pruebas. SQLite permite probar lógica y contrato HTTP, pero no acredita el comportamiento del driver, tipos o restricciones de SQL Server.

La integración de SQL Server se omite por defecto. Para habilitarla, definir explícitamente en el entorno los valores `DB_*` y `JWT_*` requeridos, usando una base ya migrada y credenciales privadas:

```powershell
$env:RUN_SQLSERVER_TESTS = '1'
python -m pytest -q -m integration_db
Remove-Item Env:\RUN_SQLSERVER_TESTS
```

La prueba de integración abre una conexión, ejecuta `SELECT 1` e inspecciona `dbo.conductores`; no crea, elimina ni actualiza datos y no carga `.env`. El resto de la suite cubre registro, normalización y duplicados; hashing y privacidad; login; claims, firma y expiración JWT; propiedad del recurso; actualizaciones permitidas; correlación; errores y UTC. El mapa detallado está en [docs/pruebas.md](docs/pruebas.md).

Importar en Postman los dos archivos de `postman/`, seleccionar **UniRide local 8081** y asignar una contraseña de prueba de al menos ocho caracteres como valor local. Ejecutar primero **Flujo contractual** y después **Casos negativos**, o la colección completa en orden. El flujo genera un correo único y guarda `conductorId` y `accessToken`; no requiere `JWT_SECRET`. No exportar contraseñas ni tokens guardados como valores locales. Véase [docs/postman.md](docs/postman.md).

## Arquitectura e integración

`controllers` maneja HTTP; `services` aplica reglas y propiedad; `repositories` consulta SQL Server; `models` define persistencia; `schemas` convierte snake_case a camelCase explícitamente; `security` implementa JWT y hashing; `exceptions` unifica errores; `middleware` conserva correlación. `app/dependencies.py` conecta componentes y facilita reemplazarlos en pruebas. `createApp()` construye la aplicación sin conectarse a la base.

Este servicio es dueño exclusivo de `unirride_usuarios`. No llama otros microservicios, no valida tokens remotamente y no expone endpoints de introspección. Tampoco contiene frontend, pasajeros, roles, API Gateway, CORS, `SERVICE_API_KEY` ni clientes HTTP de negocio. La preparación para el Gateway está documentada en [docs/integracion_gateway.md](docs/integracion_gateway.md).
