# Estado de las fases

La instrucción actual del usuario pide desarrollar todas las fases de una vez y no hacer comprobaciones. Esa instrucción sustituye las pausas de aprobación por fase del texto de referencia. Los requisitos funcionales del contrato se mantienen.

| Fase | Entregable implementado | Ejecución pendiente |
| --- | --- | --- |
| 1. Entorno | Estructura, dependencias declaradas, .gitignore, scripts PowerShell y app FastAPI. | Confirmar requisitos, crear .venv, instalar y arrancar. |
| 2. SQL Server | Settings, URL dinámica, .env privado preparado y script de creación de base. | Conectar y crear base; acordar secreto JWT compartido. |
| 3. Persistencia | Modelo, repositorio y migración de dbo.conductores. | Aplicar Alembic en SQL Server. |
| 4. Contraseñas | PasswordService con Argon2id y pruebas preparadas. | Ejecutar pruebas. |
| 5. Errores y trazabilidad | ErrorResponse, handlers, correlación y logs. | Ejecutar pruebas. |
| 6. Registro | POST /api/v1/auth/registro. | Ejecutar contra entorno preparado. |
| 7. JWT | Emisión y validación HS256; sub, iat y exp. | Ejecutar pruebas. |
| 8. Login | POST /api/v1/auth/login. | Ejecutar contra entorno preparado. |
| 9. Autenticado | GET /api/v1/auth/me. | Ejecutar contra entorno preparado. |
| 10. Consulta | GET /api/v1/conductores/{conductorId}. | Ejecutar contra entorno preparado. |
| 11. Actualización | PUT /api/v1/conductores/{conductorId}. | Ejecutar contra entorno preparado. |
| 12. pytest | Suite aislada y prueba SQL Server opcional. | Todas las ejecuciones. |
| 13. Postman | Colección v2.1 y entorno sin secretos. | Importación y ejecución. |
| 14. Gateway | Documento de rutas, headers y responsabilidades. | Implementación en otro proyecto e integración. |
| 15. README | Instalación, configuración, endpoints y operación. | Validación de los comandos en el entorno real. |

No se hicieron conexiones SQL Server, instalaciones, arranque HTTP, migraciones, pruebas pytest/Postman ni comprobaciones de servicios. No se declara que los tests pasen. Los scripts se entregan para que esas operaciones se realicen cuando se decida ejecutarlas.

Se preparó únicamente la configuración local privada, sin revelar credenciales, y un secreto JWT aleatorio. No se inicializó Git ni se crearon commits. Compartir el secreto entre equipos sigue siendo una tarea de coordinación privada.

Decisiones documentadas: Argon2id; tamaños NVARCHAR 150/254/255/30; DATETIME2(6) UTC sin zona; validación de UUID en correlación; esquema de herramientas /docs y /openapi.json, sin endpoint raíz de negocio. La decisión funcional de bloquear o permitir login de cuentas inactivas sigue pendiente de acuerdo con el equipo; no se introdujo un bloqueo adicional.
