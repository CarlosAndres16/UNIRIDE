# UniRide Frontend

Portal web del conductor para los cuatro microservicios de UniRide. Construido con React, TypeScript y Vite. El navegador consume el **API Gateway**; las bases de datos y las llamadas internas entre servicios permanecen en el backend.

Contratos revisados en [`CarlosAndres16/UNIRIDE`](https://github.com/CarlosAndres16/UNIRIDE/tree/d1114b50c039830069e977c3a49dbb3033037c68), commit `d1114b50c039830069e977c3a49dbb3033037c68`, el 13 de noviembre de 2026. Incluye la versión actualizada de Vehículos con DTO camelCase, autenticación y baja lógica.

## Inicio rápido en Windows

Requiere **Node.js 26 o posterior** y npm. Node 26 permite ejecutar las pruebas que importan módulos TypeScript directamente. Docker no es necesario para el frontend.

Desde PowerShell:

```powershell
cd 'X:\Proyecto Uniride\frontend-uniride'
npm.cmd install
Copy-Item .env.example .env.local
npm.cmd run dev
```

Abre **http://localhost:3000**. El puerto es fijo; si está ocupado, detén tu instancia anterior del frontend o configura otro puerto en `vite.config.ts`.

Como alternativa, el script prepara la configuración local si no existe, instala las dependencias faltantes e inicia Vite:

```powershell
.\scripts\iniciar.ps1
```

Si PowerShell impide ejecutar scripts, usa los comandos `npm.cmd` anteriores. No necesitas cambiar la política de ejecución del equipo.

## Configuración y conexión

Edita `.env.local`:

```dotenv
GATEWAY_URL=http://127.0.0.1:8080
VITE_API_BASE_URL=/api/v1
```

Reinicia Vite después de cambiar la configuración. `GATEWAY_URL` indica dónde está el Gateway y solo lo utiliza el proxy de Vite. `VITE_API_BASE_URL` es público y se incorpora al código del navegador durante la compilación.

Para el modo real, inicia las bases de datos y los servicios del backend conforme a sus propios README:

| Componente | Puerto habitual |
| --- | --- |
| Frontend | 3000 |
| API Gateway | 8080 |
| Usuarios y autenticación | 8081 |
| Vehículos | 8082 |
| Viajes | 8083 |
| Reservas y estadísticas | 8084 |

Las solicitudes siguen este recorrido:

```text
Navegador :3000 → proxy /api de Vite → Gateway :8080 → microservicio
```

El proxy conserva las rutas `/api/v1/...`. Al usar la base relativa predeterminada, el navegador se comunica con su mismo origen y evita peticiones CORS directas a cada microservicio. Si eliges una URL absoluta para `VITE_API_BASE_URL`, el Gateway debe permitir explícitamente el origen del frontend mediante `FRONTEND_ORIGIN`.

Si el Gateway corre en el equipo de un compañero, usa una dirección accesible desde el equipo que ejecuta Vite, por ejemplo `GATEWAY_URL=http://192.168.1.50:8080`. Esa dirección es un ejemplo: reemplázala por la real. El Gateway debe escuchar en una interfaz accesible y el firewall debe permitir la conexión. Los servicios internos pueden seguir en Docker o ejecutarse localmente.

**No copies `JWT_SECRET`, `SERVICE_API_KEY` ni credenciales de bases de datos al frontend.** Son configuración exclusiva del backend. Para iniciar sesión utiliza el correo y la contraseña de una cuenta de Usuarios.

## Funcionalidades

| Pantalla | Funcionalidad |
| --- | --- |
| Acceso | Registro de conductor, inicio de sesión y entrada a la demostración |
| Inicio | Resumen de actividad, próximos viajes y acceso a reservas |
| Mis vehículos | Consultar, registrar, editar y desactivar vehículos propios |
| Mis viajes | Consultar con filtros y paginación, publicar, editar, cancelar y finalizar |
| Reservas | Consultar reservas por viaje y filtrar por estado |
| Estadísticas | Consultar por conductor, vehículo o viaje; periodo de fechas cuando corresponde |
| Mi perfil | Consultar y actualizar nombre y teléfono |

La baja de Vehículos utiliza `DELETE` y conserva el registro como `INACTIVO` en el servicio. Las reservas son de consulta: el contrato actual no ofrece operaciones para crearlas o modificarlas desde este portal. El alcance corresponde al conductor; no incluye cuentas de pasajeros, pagos, chat ni GPS en tiempo real.

El cliente envía JWT Bearer y un UUID de correlación por solicitud. La publicación de viajes utiliza `Idempotency-Key`; su edición envía `If-Match` con la versión del viaje. No se hacen reintentos automáticos de escrituras: si una solicitud tarda demasiado, consulta primero el estado del registro.

## Demostración sin backend

En el acceso selecciona la opción de demostración. Los datos son **ficticios**, el modo está señalado en la interfaz y no realiza llamadas al Gateway. Permite recorrer las pantallas y modificar ejemplos en memoria; al recargar se restablecen los datos iniciales.

La demostración permite revisar la experiencia visual y los flujos locales. No verifica las bases de datos, los JWT reales ni la integración entre microservicios. Sal de la demostración y usa una cuenta del backend para comprobar el flujo real.

## Sesión y errores

La sesión real utiliza `sessionStorage` de la pestaña. Se elimina al cerrar sesión, expirar el tiempo informado por el backend o recibir una respuesta `401`. Las claves de firma nunca se solicitan en el navegador. La autorización definitiva corresponde a cada microservicio.

Los errores muestran un mensaje y, cuando está disponible, una referencia de correlación para localizar la petición en los registros. Un `409` o `412` al editar requiere actualizar los datos antes de reintentar.

En la revisión del backend se observó que las lecturas de Viajes todavía requieren reforzar la autorización de propietario. El frontend fuerza el filtro del conductor actual y rechaza viajes de otra cuenta, pero esta comprobación no reemplaza la autorización del microservicio. Esa corrección sigue siendo necesaria antes de exponer el sistema públicamente.

## Compilación y pruebas

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run preview
```

`npm test` ejecuta las pruebas aisladas del transporte HTTP y del adaptador de demostración. `npm run build` comprueba TypeScript y genera `dist/`. `npm run preview` sirve esa compilación localmente y utiliza el mismo proxy al Gateway. Las pruebas aisladas no sustituyen la comprobación con los cuatro servicios y sus bases de datos.

Para validar la integración real:

1. Inicia el Gateway y los cuatro microservicios y confirma la URL configurada.
2. Registra una cuenta o inicia sesión con una existente.
3. Registra un vehículo, edítalo y publica un viaje con él.
4. Consulta el viaje, modifica sus datos y revisa la sección de reservas.
5. Consulta las estadísticas del conductor, el vehículo y el viaje. Las reservas dependen de los datos existentes en el servicio de Reservas.
6. Finaliza o cancela un viaje activo y verifica su estado. Desactiva únicamente un vehículo de prueba que ya no necesites.
7. Cierra sesión y verifica que regrese la pantalla de acceso.

Estas acciones escriben datos reales en los servicios correspondientes; utiliza una cuenta y registros destinados a pruebas.

## Despliegue

Los archivos de `dist/` se pueden servir con un servidor web. Configura un proxy inverso para `/api` hacia el Gateway, conservando `/api/v1/...`, o compila con la URL pública del Gateway en `VITE_API_BASE_URL` y configura su CORS.

`vite preview` sirve para revisar la compilación local. Para un despliegue público utiliza un servidor de producción con HTTPS tanto en el acceso web como en las conexiones públicas a la API. Una página HTTPS no puede consumir un Gateway HTTP directamente desde el navegador.

Sube `frontend-uniride` como carpeta junto a los microservicios en el repositorio. Incluye `package-lock.json` para instalaciones reproducibles con `npm.cmd ci`. Excluye `node_modules`, `dist` y archivos `.env.local`; el ejemplo de configuración sí se conserva.

## Estructura

```text
src/
  components/      Formularios, diálogos y elementos reutilizables
  pages/           Pantallas del portal
  lib/api.ts       Operaciones contra el Gateway
  lib/http.ts      Transporte, correlación, timeout y errores
  lib/demo.ts      Adaptador de datos ficticios en memoria
  types.ts         Contratos de datos
tests/             Pruebas aisladas
scripts/           Inicio en PowerShell
vite.config.ts     Servidor local y proxy
.env.example       Configuración pública de ejemplo
```

## Problemas frecuentes

- **No conecta al iniciar sesión:** comprueba que el Gateway escucha en `GATEWAY_URL`; reinicia Vite si cambiaste `.env.local`.
- **La página abre, pero un módulo falla:** revisa el servicio correspondiente y su base de datos. El frontend no inicia automáticamente el backend.
- **La sesión termina:** vuelve a iniciar sesión. Todos los servicios deben compartir el secreto de firma acordado en su configuración privada.
- **Hay vehículos, pero no pueden utilizarse en Viajes:** revisa que estén activos y que Viajes tenga la URL real del servicio de Vehículos.
- **Reservas o estadísticas devuelven un error:** revisa sus dependencias de Viajes y Vehículos y el `SERVICE_API_KEY` privado utilizado entre Reservas y Viajes.
- **Aparece `ModuleNotFoundError: app`:** es un problema del arranque del microservicio Python. Ejecútalo desde la carpeta de ese servicio con el comando de su README; el frontend se inicia con `npm.cmd run dev`.
