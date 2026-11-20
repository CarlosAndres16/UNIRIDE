# API Gateway de UniRide

Punto de entrada público a las APIs. Conserva las rutas `/api/v1/...`, el JSON del cuerpo y las cabeceras Bearer, correlación, Idempotency-Key e If-Match. No consume ni registra contraseñas, tokens ni cuerpos de las peticiones. La ruta de ocupación está reservada a llamadas directas entre Viajes y Reservas.

Desde la raíz del repositorio:

```powershell
.\scripts\Configurar-Hamachi.ps1 -Servicio Gateway
.\scripts\Iniciar-Servicio.ps1 -Servicio Gateway -Instalar
```

Las URLs de los cuatro servicios se obtienen de `config/hamachi.json`. El configurador escribe `.env` local; el Gateway no necesita `JWT_SECRET`, `SERVICE_API_KEY` ni credenciales de base de datos. `SERVER_HOST` vale `0.0.0.0` por defecto y `SERVER_PORT` vale 8080. `FRONTEND_ORIGIN` admite orígenes HTTP separados por comas.

`GET /health` verifica el proceso. `GET /health/ready` consulta el readiness de las cuatro APIs en paralelo con timeout y devuelve 503 si alguna no está preparada. Solo devuelve nombres de servicios y estados, sin cadenas de conexión. `GATEWAY_TIMEOUT_MS` limita el proxy; `READINESS_TIMEOUT_MS` limita cada comprobación.

Desde esta carpeta, `npm ci` instala dependencias y `npm test` ejecuta la integración del proxy con cuatro proveedores HTTP locales simulados. No requiere bases de datos ni secretos reales.
