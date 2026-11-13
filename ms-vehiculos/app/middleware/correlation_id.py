"""X-Correlation-Id (D-17): se acepta, se genera si falta y se devuelve siempre."""

import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.exceptions.handlers import unexpectedExceptionHandler

logger = logging.getLogger("uniride.requests")


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        recibidos = [
            valor.decode("latin-1")
            for clave, valor in scope.get("headers", [])
            if clave.lower() == b"x-correlation-id"
        ]
        correlationId = str(uuid4())
        if len(recibidos) == 1:
            try:
                UUID(recibidos[0])
                correlationId = recibidos[0]
            except ValueError:
                pass  # encabezado inválido: se genera uno nuevo
        scope.setdefault("state", {})["correlationId"] = correlationId
        inicio = perf_counter()
        estado = 500
        respuestaIniciada = False

        async def enviarConCorrelacion(message: Message) -> None:
            nonlocal estado, respuestaIniciada
            if message["type"] == "http.response.start":
                respuestaIniciada = True
                estado = message["status"]
                MutableHeaders(scope=message)["X-Correlation-Id"] = correlationId
            await send(message)

        try:
            try:
                await self.app(scope, receive, enviarConCorrelacion)
            except Exception as exc:
                if respuestaIniciada:
                    raise
                respuesta = await unexpectedExceptionHandler(Request(scope, receive), exc)
                await respuesta(scope, receive, enviarConCorrelacion)
        finally:
            ruta = getattr(scope.get("route"), "path", "ruta-no-registrada")
            logger.info(
                "%s %s status=%s duracionMs=%.1f correlationId=%s",
                scope["method"], ruta, estado,
                (perf_counter() - inicio) * 1000, correlationId,
            )
