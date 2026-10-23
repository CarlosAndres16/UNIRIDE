"""Identificacion de solicitudes HTTP con contexto aislado para cada tarea."""

from contextvars import ContextVar
import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.schemas.error_schema import CodigoError, DetalleError, ErrorResponse

HEADER_CORRELATION_ID = "X-Correlation-Id"
correlationIdContext: ContextVar[str | None] = ContextVar("correlationId", default=None)
logger = logging.getLogger("uniride.http")


def getCorrelationId() -> str | None:
    """Permite a logs y futuros clientes obtener el UUID de esta solicitud."""

    return correlationIdContext.get()


class ErrorRespuestaIniciada(RuntimeError):
    """Interrumpe una respuesta incompleta sin propagar el mensaje privado."""

    def __init__(self, correlationId: str) -> None:
        super().__init__(
            "Fallo despues de iniciar la respuesta. correlationId=" + correlationId
        )


class CorrelationIdMiddleware:
    """Middleware ASGI puro; no comparte estado mutable entre solicitudes."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headerValues = [
            value for name, value in scope.get("headers", [])
            if name.lower() == b"x-correlation-id"
        ]
        invalidHeader = False
        if not headerValues:
            correlationId = str(uuid4())
        else:
            try:
                if len(headerValues) != 1:
                    raise ValueError("Header duplicado")
                correlationId = str(UUID(headerValues[0].decode("ascii")))
            except (ValueError, UnicodeDecodeError):
                correlationId = str(uuid4())
                invalidHeader = True

        scope.setdefault("state", {})["correlationId"] = correlationId
        token = correlationIdContext.set(correlationId)
        startedAt = perf_counter()
        statusCode = 500
        responseStarted = False

        async def sendWithCorrelation(message: Message) -> None:
            nonlocal statusCode, responseStarted
            if message["type"] == "http.response.start":
                responseStarted = True
                statusCode = message["status"]
                MutableHeaders(scope=message)[HEADER_CORRELATION_ID] = correlationId
            await send(message)

        try:
            if invalidHeader:
                error = ErrorResponse(
                    status=400,
                    error=CodigoError.FORMATO_INVALIDO,
                    message="X-Correlation-Id debe contener un unico UUID valido.",
                    path=scope.get("path") or "/",
                    correlationId=correlationId,
                    detalles=[DetalleError(
                        campo=HEADER_CORRELATION_ID,
                        problema="Debe enviarse una sola vez y contener un UUID valido.",
                    )],
                )
                logger.warning("error=%s status=400", CodigoError.FORMATO_INVALIDO)
                response = JSONResponse(
                    error.model_dump(mode="json", exclude_none=True), status_code=400
                )
                await response(scope, receive, sendWithCorrelation)
                return

            await self.app(scope, receive, sendWithCorrelation)
        except Exception as error:
            if responseStarted:
                logger.error(
                    "Fallo despues de iniciar respuesta tipo=%s",
                    type(error).__name__,
                )
                # No se puede cambiar una respuesta que ya envio sus headers.
                # Evitar que Uvicorn registre mensajes privados de la causa.
                raise ErrorRespuestaIniciada(correlationId) from None

            # Responder antes del ServerErrorMiddleware evita que Uvicorn vuelva
            # a registrar la excepcion original con valores internos sensibles.
            from app.exceptions.handlers import manejarErrorInterno

            response = await manejarErrorInterno(Request(scope), error)
            await response(scope, receive, sendWithCorrelation)
        finally:
            try:
                path = scope.get("path", "/")
                safePath = path.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
                logger.info(
                    "http method=%s path=%s status=%s duration_ms=%.2f",
                    scope.get("method", ""),
                    safePath,
                    statusCode,
                    (perf_counter() - startedAt) * 1000,
                )
            finally:
                correlationIdContext.reset(token)
