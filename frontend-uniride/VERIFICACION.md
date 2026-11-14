# Verificación del frontend

Revisión realizada el 13 de noviembre de 2026 sobre los contratos del commit `d1114b50c039830069e977c3a49dbb3033037c68` de UNIRIDE.

## Comprobaciones realizadas

- `npm.cmd run build`: aprobado. Comprobación estricta de TypeScript y compilación de producción con Vite.
- `npm.cmd test`: 14 pruebas aprobadas, sin fallos ni omisiones. Cubren transporte HTTP, correlación, respuestas vacías, errores, timeout sin repetir escrituras y flujos del adaptador de demostración.
- Navegador Chrome: acceso al portal, entrada a la demostración, registro de vehículo ficticio, publicación de viaje con coordenadas, selección de viaje, reservas, ocupación y estadísticas.
- Revisión visual de escritorio y vista móvil de 390 × 844. Se restableció el tamaño del navegador al terminar.
- Las operaciones de navegador se realizaron únicamente en el modo de demostración, que guarda datos en memoria. Se recargó la página para restablecer el conjunto inicial después de las pruebas.

## Validación pendiente con el equipo

No se ejecutó la integración completa con Gateway, los cuatro microservicios y las bases de datos reales. Es necesario encenderlos, compartir la configuración privada entre los servicios y seguir el recorrido de comprobación del README usando registros de prueba.

Las claves privadas y las bases de datos permanecen en el backend. La revisión no modificó ni publicó archivos de los microservicios en GitHub.
