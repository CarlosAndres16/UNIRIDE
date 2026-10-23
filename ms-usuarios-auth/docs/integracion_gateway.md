# Integración prevista con API Gateway

Esta fase entrega el contrato de enrutamiento. No implementa ni despliega el Gateway.

| Entrada en Gateway | Destino | Transformación |
| --- | --- | --- |
| `/api/v1/auth/**` | `http://ms-usuarios-auth:8081` | Conservar ruta y método completos. |
| `/api/v1/conductores/**` | `http://ms-usuarios-auth:8081` | Conservar ruta y método completos. |

En desarrollo sin resolución DNS de servicios, el upstream puede ser `http://localhost:8081`. El frontend se integrará con el Gateway; Postman y las herramientas locales pueden acceder directamente al servicio.

El Gateway debe conservar `Authorization: Bearer <JWT>`, `X-Correlation-Id`, Content-Type, códigos de estado y cuerpos. Debe devolver al cliente el header `X-Correlation-Id` producido por el servicio, incluidos errores. Si genera la correlación en la entrada, debe usar un UUID válido y conservarlo en todo el trayecto. No eliminar el prefijo `/api/v1` ni reemplazar `ErrorResponse` por una respuesta incompatible.

El login y registro son públicos. Las otras tres rutas requieren JWT. El Gateway no valida JWT: enruta la solicitud y conserva el header Authorization. Cada microservicio valida HS256, firma, expiración y `sub` localmente con el mismo `JWT_SECRET` privado, sin consultar a Usuarios. La propiedad se compara entre `conductorId` del recurso y `sub`.

En el repositorio del Gateway, el contrato utiliza `USUARIOS_SERVICE_URL=http://localhost:8081` y `SERVER_PORT=8080`. Esos valores corresponden a su configuración; aquí `SERVER_PORT=8081`. La vigencia se controla en Usuarios con `JWT_EXPIRES_IN_SECONDS`. Los equipos deben acordar el secreto por un canal privado y coordinar sus cambios.

CORS corresponde al Gateway. Este proyecto no configura orígenes, preflight ni credenciales CORS y no introduce clientes de otros servicios ni claves `SERVICE_API_KEY`/`X-Service-Key`.

La integración real queda pendiente de tener Gateway y servicios en ejecución; no se efectuaron llamadas ni verificaciones de red durante esta entrega.
