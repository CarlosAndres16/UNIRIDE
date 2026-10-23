"""Ensamblaje HTTP; no crea tablas ni abre conexiones al importar."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.config.database import getEngine
from app.controllers.auth_controller import router as authRouter
from app.controllers.conductor_controller import router as conductorRouter
from app.exceptions.handlers import registerExceptionHandlers
from app.middleware.correlation_id import CorrelationIdMiddleware, CorrelationLogFilter


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # No se conecta ni se ejecutan migraciones durante el arranque.
    if getEngine.cache_info().currsize:
        getEngine().dispose()


def createApp() -> FastAPI:
    app = FastAPI(
        title="UniRide - Usuarios y Autenticación",
        description="Registro, login JWT y datos del conductor. Contrato común v1.0.",
        version="1.0.0",
        lifespan=lifespan,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        swagger_ui_parameters={"persistAuthorization": False},
        redirect_slashes=False,
    )
    app.add_middleware(CorrelationIdMiddleware)
    registerExceptionHandlers(app)
    app.include_router(authRouter)
    app.include_router(conductorRouter)

    def customOpenApi():
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )
            # FastAPI documenta 422 por defecto; nuestro contrato responde 400.
            for path in schema["paths"].values():
                for operation in path.values():
                    if isinstance(operation, dict) and "responses" in operation:
                        responses = operation["responses"]
                        responses.pop("422", None)
                        responses.setdefault(
                            "400",
                            {
                                "description": "Solicitud inválida",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                    }
                                },
                            },
                        )
                        responses.setdefault(
                            "500",
                            {
                                "description": "Error interno",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                    }
                                },
                            },
                        )
                        operation.setdefault("parameters", []).append(
                            {
                                "name": "X-Correlation-Id",
                                "in": "header",
                                "required": False,
                                "description": "UUID conservado durante toda la solicitud.",
                                "schema": {"type": "string", "format": "uuid"},
                            }
                        )
                        for response in responses.values():
                            response.setdefault("headers", {})["X-Correlation-Id"] = {
                                "description": "UUID recibido o generado por el servicio.",
                                "schema": {"type": "string", "format": "uuid"},
                            }
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = customOpenApi
    return app


def configureLogging() -> None:
    logger = logging.getLogger("uniride")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(CorrelationLogFilter())
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s correlationId=%(correlationId)s %(message)s"
            )
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


configureLogging()
app = createApp()
