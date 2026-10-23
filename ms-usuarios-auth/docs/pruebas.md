# Cobertura preparada

La suite es código entregado, **no un reporte de ejecución**. No se corrieron pruebas ni comprobaciones por instrucción del usuario.

| Requisito solicitado | Archivo y escenario |
| --- | --- |
| 1. Conexión SQL Server | `test_sqlserver_integration.py`: SELECT 1 e inspección contractual; opt-in de solo lectura. |
| 2–5. Crear, normalizar correo, duplicado y password mínimo | `test_api.py`: registro 201, correo persistido en minúsculas, 409 case-insensitive, 400 y límite de ocho caracteres. |
| 6–7. Hash y privacidad | `test_api.py`: hash Argon2id almacenado, verificación, respuesta y logs sin contraseña, validación sin reflejar valores. |
| 8–11. Login | `test_api.py`: login correcto, normalización, correo/password incorrectos y mismo mensaje genérico. |
| 12–17. Claims y vigencia | `test_security.py`: claims exactos, sub textual, iat/exp enteros, HS256, TTL predeterminado y configurable. |
| 18–19. JWT inválido y vencido | `test_security.py`: firma, algoritmo, expiración, claims ausentes, sub inválido y header Bearer. |
| 20. GET me | `test_api.py`: identidad del JWT; query no cambia la identidad. |
| 21–23. Consulta y propiedad | `test_api.py`: propio 200, ajeno 403, identidad propia inexistente 404. |
| 24–27. Actualización | `test_api.py`: actualiza nombre y teléfono, acepta null, ajeno 403, requiere nombre, inexistente 404. |
| 28–29. Campos protegidos | `test_api.py`: parametrización de correo, activo, identificadores, hashes, contraseña y fechas adicionales rechazadas. |
| 30–32. Correlación y errores | `test_api.py`: UUID conservado/generado, logs, ErrorResponse, correlación inválida y 500 sin detalles internos. |
| 33. UTC | `test_api.py`: timestamp de ErrorResponse con zona UTC y persistencia UTC naive. |

Pruebas adicionales: teléfono omitido/null, datos inválidos, salt aleatoria, hash corrupto y contraseña Unicode de más de 72 bytes. Las parametrizaciones amplían los escenarios por encima del mínimo solicitado.

Las fixtures usan `Settings(_env_file=None)` con datos sintéticos y precargan el caché de configuración antes de importar la aplicación. Sustituyen `getSession` y `getSettings`. Se crea una base SQLite por prueba con `StaticPool` y `schema_translate_map={"dbo": None}`. La creación automática de tablas se limita a esa base efímera. No se conecta al motor SQL Server en las pruebas aisladas.

La prueba SQL Server solo se habilita con `RUN_SQLSERVER_TESTS=1`, usa variables de entorno explícitas y requiere migraciones ya aplicadas. No lee `.env`. No prueba inserciones concurrentes ni reemplaza una ejecución completa sobre el motor real; inspecciona existencia, columnas, longitudes, nullability y restricción única de correo.
