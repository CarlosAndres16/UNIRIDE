"""Rutas exigidas por el contrato, independientes del registro de FastAPI."""

RUTAS_CONTRATO = {
    "/api/v1/reservas/viaje/{viajeId}",
    "/api/v1/reservas/{reservaId}",
    "/api/v1/estadisticas/viaje/{viajeId}",
    "/api/v1/estadisticas/conductor/{conductorId}",
    "/api/v1/estadisticas/vehiculo/{vehiculoId}",
}
