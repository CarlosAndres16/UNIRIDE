import logging

from fastapi import FastAPI

from app.controllers.vehiculo_controller import router as vehiculoRouter
from app.exceptions.handlers import registerExceptionHandlers
from app.middleware.correlation_id import CorrelationIdMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="UniRide - ms-vehiculos",
    description="Registro, consulta, modificación y baja de los vehículos del conductor.",
    version="1.0.0",
)
app.add_middleware(CorrelationIdMiddleware)
registerExceptionHandlers(app)
app.include_router(vehiculoRouter)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    """Solo para Docker/monitoreo; no forma parte de los 22 endpoints del contrato."""
    return {"status": "ok", "servicio": "ms-vehiculos"}
