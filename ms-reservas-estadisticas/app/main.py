
from fastapi import FastAPI

from app.config.logging_config import configurarLogging
from app.config.settings import getSettings
from app.controllers.estadistica_controller import router as estadisticaRouter
from app.controllers.reserva_controller import router as reservaRouter
from app.exceptions.handlers import registrarManejadores
from app.middleware.correlation_id import CorrelationIdMiddleware


def crearAplicacion() -> FastAPI:
    configurarLogging()
    application = FastAPI(
        title="UniRide - Reservas y Estadísticas",
        description=(
            "Consulta de reservas y estadisticas de los viajes del conductor "
            "autenticado. Las reservas son de solo lectura en la version 1."
        ),
        version="1.0.0",
        redoc_url=None,
    )
    registrarManejadores(application)
    application.add_middleware(CorrelationIdMiddleware)
    application.include_router(reservaRouter)
    application.include_router(estadisticaRouter)
    return application


app = crearAplicacion()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        port=getSettings().serverPort,
        reload=True,
        access_log=False,
    )
