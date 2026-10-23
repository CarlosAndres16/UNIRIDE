# Colección Postman

Archivos importables en Postman:

- `postman/UniRide-Usuarios-Auth.postman_collection.json`: colección v2.1 con los cinco endpoints y casos negativos.
- `postman/UniRide-local.postman_environment.json`: entorno local con `baseUrl=http://localhost:8081`, sin credenciales ni tokens prellenados.

Para usarla cuando el servidor y la base estén preparados:

1. Importar ambos archivos y seleccionar el entorno **UniRide local 8081**.
2. Asignar `password` como valor local de tipo secreto, con al menos ocho caracteres. No guardar una contraseña real del usuario.
3. Ejecutar **Flujo contractual** en orden. El registro genera un correo de prueba único y guarda el `conductorId`. Login guarda el `accessToken`.
4. Ejecutar **Casos negativos** con el mismo entorno: duplicado 409; password corto 400; credenciales incorrectas 401; falta de token y token inválido 401; recurso ajeno GET/PUT 403; modificación de correo y activo 400.
5. Revisar los resultados de los scripts de Postman y limpiar `password` y `accessToken` al terminar.

Cada solicitud utiliza un UUID de correlación. Los scripts comprueban el status, el header de correlación, los campos públicos y la ausencia de campos de contraseña. Los casos negativos validan la forma de `ErrorResponse`. El caso de recurso ajeno utiliza el identificador máximo de SQL INT; presupone que el conductor recién registrado no tiene ese ID.

La colección crea y actualiza un conductor de prueba. No implementa eliminación de datos porque el contrato no incluye un endpoint DELETE. Usar una base de desarrollo y limpiar los datos solo mediante el procedimiento acordado por el equipo.

Esta colección se creó como artefacto; **no se importó, ejecutó ni certificó en Postman** durante la entrega. No exportar un entorno con valores locales sensibles. No es necesario conocer `JWT_SECRET` ni credenciales SQL Server para utilizar la API.
