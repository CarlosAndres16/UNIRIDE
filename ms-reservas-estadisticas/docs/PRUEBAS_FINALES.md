# Pruebas finales — UniRide Reservas y Estadísticas

Ejecución del **22 de octubre de 2026**, con Python **3.13.2** y pytest **9.1.1**.
Resultado consolidado: **232 pruebas aprobadas, 0 fallos y 261 subcasos aprobados**.
Los subcasos pertenecen a las regresiones y no se suman como otros tests pytest.
La ejecución consolidada terminó con código 0 y duración informada de 9,72 segundos.

## Alcance comprobado

| Grupo | Pruebas | Contenido |
| --- | ---: | --- |
| Regresiones | 121 | HTTP, errores, JWT, mocks, clientes, listado por viaje y privacidad |
| Aceptación final | 98 | Cinco endpoints, detalle, estadísticas, fechas, paginación, autorización y ocupación |
| Repositorio | 10 | Agregación parametrizada, estados, sumas, datos inválidos y lotes de IDs |
| SQL Server real | 3 | Base y migración, lecturas del repositorio y los cinco endpoints con SQL real |
| **Total** | **232** | **Todo aprobado** |

Los tests de aceptación usan los controladores, servicios, validación JWT y
clientes HTTP reales. Las peticiones de los clientes se envían por transportes
ASGI a los mocks dentro del mismo proceso, sin sockets de red. Las reservas se
simulan en memoria, salvo en los tres tests SQL, que utilizan el repositorio y
la base SQL Server reales. El verificador de repositorio también inspecciona
el SQL compilado para el dialecto de SQL Server.

Las credenciales de pruebas se generan aleatoriamente en memoria y se descartan.
No se modifica `.env`, no se insertan ni actualizan reservas, no se detienen los
servidores del usuario y no se consulta la base de otro microservicio.

## Cómo ejecutarlas

Desde PowerShell, instala pytest si es una copia nueva:

```powershell
Set-Location 'X:\Proyecto Uniride\ms-reservas-estadisticas'
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

La suite habitual no requiere SQL Server, secretos acordados ni servidores abiertos:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Omite los tres tests SQL mediante la marca `sql_server`. Para incluirlos y generar
el mismo informe de la ejecución final:

```powershell
.\.venv\Scripts\python.exe -m pytest --sql-server -q --junitxml=reports/pruebas-finales.xml
```

Las pruebas SQL requieren la configuración privada existente, el servicio SQL
disponible, la migración `0001_crear_reservas` y reservas del seed en el viaje 305.
No ejecutan automáticamente el seed ni las migraciones.

Para mostrar cada caso por separado, sustituye `-q` por `-v`. Un código de salida
0 indica aprobación; cualquier otro código requiere revisar la salida de pytest.

## Casos de aceptación principales

| Escenario | Resultado comprobado |
| --- | --- |
| Swagger / OpenAPI | Publica exactamente cinco GET protegidos y sin 422 documentados |
| Token ausente, inválido, vencido o de otra firma | 401 antes de consultar las dependencias |
| Recursos ajenos en las cinco rutas | 403, sin devolver datos del pasajero |
| Reserva, viaje o vehículo inexistente | 404 con el código del recurso |
| POST, PUT, PATCH y DELETE en las cinco rutas | 405, sin ejecutar los servicios |
| Detalle de reserva | DTO completo, fecha UTC y autorización antes del resumen |
| Viaje 305 con el escenario básico | 3 reservas, 2 confirmadas, 1 cancelada, 2 pasajeros, 2 cupos disponibles, 50 % |
| Agregado de conductor 25 en el escenario básico | 3 viajes incluidos, 2 vehículos y ocupación ponderada del 20 % |
| Agregado de vehículo 12 en el escenario básico | 2 viajes incluidos, capacidad acumulada 8 y ocupación del 25 % |
| Reservas de un viaje CANCELADO | Excluidas de los agregados |
| Fecha inicial / final igual a la salida | Límites inclusivos |
| Fecha parcial | Extremo omitido como null en periodo |
| Fechas invertidas, imposibles o con timestamp | 400 antes de HTTP y SQL |
| Vehículo propio INACTIVO sin viajes | 200 con contadores y porcentaje en cero |
| Conductor 27 con 51 viajes | Recorre páginas 1 y 2; incluye la reserva del último viaje |
| Reserva confirmada con varios cupos | Suma cupos, no solo cantidad de reservas |
| Filtro de listado por estado | No reduce el total confirmado enviado a Viajes |
| GET a dependencia | JWT del conductor y el mismo UUID; sin llave interna |
| PUT interno de ocupación | Total absoluto, llave interna y UUID; sin JWT |
| Ocupación ya coincidente | Evita repetir el PUT |
| PUT con timeout, caída o respuesta inválida | Reintenta una vez, conserva el 200 y recupera en la siguiente consulta |
| Llave interna rechazada | Conserva la consulta válida del conductor |
| Viaje FINALIZADO o CANCELADO | No actualiza ocupación |
| Sobreocupación | Conserva pasajeros reales, disponibilidad mínima 0 y porcentaje máximo 100 |
| Dependencia caída, timeout o DTO inválido en lectura | 503 tras los dos intentos permitidos, sin consultar SQL |
| Error SQL | 500 genérico, sin exponer el mensaje interno |
| Capacidad cero / redondeo | 0 defensivo y redondeo a dos decimales |
| Más de 2100 IDs | Consultas agrupadas en bloques de 1000, sin duplicar viajes |

Estos valores numéricos corresponden al escenario determinista de las pruebas
aisladas. Las pruebas SQL contrastan los datos existentes con consultas SQL de
lectura y no presuponen que otra instalación tenga los mismos IDs de reserva.

## Informes y advertencia

`reports/pruebas-finales.xml` contiene el resultado JUnit consolidado. El XML
contabiliza 493 entradas porque incluye las 232 pruebas y sus 261 subcasos:
493 entradas, 0 fallos, 0 errores y 0 omitidas. La consola de pytest muestra
por separado `232 passed` y `261 subtests passed`.
Los informes parciales corresponden a las ejecuciones previas de los mismos grupos;
sus cantidades no deben sumarse nuevamente al consolidado.

Se emitió una advertencia de deprecación de Starlette por el uso de httpx con
TestClient. No produjo fallos ni requirió cambiar las dependencias productivas.

## Límite del resultado

Esta entrega comprueba el comportamiento local y las lecturas de SQL Server.
No verifica todavía los servidores reales de Usuarios, Viajes, Vehículos ni el
Gateway del equipo. Esa integración necesita los secretos acordados, las URLs,
un JWT real e IDs coherentes. La colección Postman está preparada para esa etapa;
no se ejecutó contra servicios reales.
