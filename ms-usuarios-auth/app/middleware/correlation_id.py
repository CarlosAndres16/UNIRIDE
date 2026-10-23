"""Middleware ASGI que conserva el UUID incluso en errores inesperados."""

import logging
from contextvars import ContextVar
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.exceptions.handlers import errorResponse, unexpectedExceptionHandler

correlationIdContext: ContextVar[str] = ContextVar("correlationId", default="-")
logger = logging.getLogger("uniride.requests")


class CorrelationLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlationId = correlationIdContext.get()
        return True


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = [
            value.decode("latin-1")
            for key, value in scope.get("headers", [])
            if key.lower() == b"x-correlation-id"
        ]
        invalidHeader = len(supplied) > 1
        correlationId = str(uuid4())
        if len(supplied) == 1:
            try:
                UUID(supplied[0])
                correlationId = supplied[0]
            except ValueError:
                invalidHeader = True
        scope.setdefault("state", {})["correlationId"] = correlationId
        contextToken = correlationIdContext.set(correlationId)
        startedAt = perf_counter()
        responseStarted = False
        status = 500

        async def sendWithCorrelation(message: Message) -> None:
            nonlocal responseStarted, status
            if message["type"] == "http.response.start":
                responseStarted = True
                status = message["status"]
                MutableHeaders(scope=message)["X-Correlation-Id"] = correlationId
            await send(message)

        try:
            if invalidHeader:
                response = errorResponse(
                    Request(scope, receive),
                    400,
                    "FORMATO_INVALIDO",
                    "X-Correlation-Id debe contener un único UUID válido.",
                    [{"campo": "X-Correlation-Id", "problema": "Debe ser un UUID válido."}],
                )
                await response(scope, receive, sendWithCorrelation)
                return
            try:
                await self.app(scope, receive, sendWithCorrelation)
            except Exception as exc:
                if responseStarted:
                    # Las rutas de este servicio no producen respuestas en streaming.
                    raise
                response = await unexpectedExceptionHandler(Request(scope, receive), exc)
                await response(scope, receive, sendWithCorrelation)
        finally:
            route = scope.get("route")
            # La plantilla evita registrar datos introducidos en URL, query o body.
            routeName = getattr(route, "path", "ruta-no-registrada")
            logger.info(
                "%s %s status=%s duracionMs=%.1f correlationId=%s",
                scope["method"],
                routeName,
                status,
                (perf_counter() - startedAt) * 1000,
                correlationId,
            )
            correlationIdContext.reset(contextToken)
