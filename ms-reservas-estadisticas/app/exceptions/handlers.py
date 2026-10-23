"""Traduce excepciones del servicio a respuestas publicas sin datos internos."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.exceptions.exceptions import ExcepcionAplicacion
from app.middleware.correlation_id import HEADER_CORRELATION_ID, getCorrelationId
from app.schemas.error_schema import CodigoError, DetalleError, ErrorResponse

logger = logging.getLogger("uniride.errors")


def getRequestCorrelationId(request: Request) -> str:
    correlationId = getattr(request.state, "correlationId", None) or getCorrelationId()
    if correlationId is None:
        correlationId = str(uuid4())
        request.state.correlationId = correlationId
    return correlationId


def responderError(request: Request, error: ExcepcionAplicacion) -> JSONResponse:
    correlationId = getRequestCorrelationId(request)
    response = ErrorResponse(
        status=error.status,
        error=error.error,
        message=error.message,
        path=request.scope.get("path") or "/",
        correlationId=correlationId,
        detalles=error.detalles,
    )
    level = logging.ERROR if error.status >= 500 else logging.WARNING
    logger.log(
        level,
        "error=%s status=%s",
        error.error,
        error.status,
        extra={"correlationId": correlationId},
    )
    headers = {HEADER_CORRELATION_ID: correlationId}
    if error.status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        response.model_dump(mode="json", exclude_none=True),
        status_code=error.status,
        headers=headers,
    )


async def manejarExcepcionAplicacion(request: Request, error: ExcepcionAplicacion):
    return responderError(request, error)


def describirValidacion(issue: dict) -> tuple[CodigoError, DetalleError]:
    """No copia input, ctx ni mensajes personalizados que puedan revelar datos."""

    errorType = issue.get("type", "")
    location = list(issue.get("loc", ()))
    if location and location[0] in ("body", "query", "path", "header", "cookie"):
        location.pop(0)
    campo = ".".join(str(part) for part in location) or "solicitud"

    if errorType == "missing":
        code, problem = CodigoError.CAMPO_OBLIGATORIO_FALTANTE, "El campo es obligatorio."
    elif errorType.startswith(("date_", "datetime_", "time_")):
        code, problem = CodigoError.FECHA_HORA_INVALIDA, "La fecha u hora no es valida."
    elif errorType == "json_invalid":
        campo = "body"
        code, problem = CodigoError.FORMATO_INVALIDO, "El cuerpo debe contener JSON valido."
    elif errorType.endswith(("_parsing", "_type")) or errorType in ("enum", "literal_error"):
        code, problem = CodigoError.FORMATO_INVALIDO, "El formato del campo no es valido."
    else:
        code, problem = CodigoError.SOLICITUD_INVALIDA, "El valor no cumple las restricciones del campo."
    return code, DetalleError(campo=campo, problema=problem)


async def manejarValidacion(request: Request, error: RequestValidationError):
    descriptions = [describirValidacion(issue) for issue in error.errors()]
    priority = (
        CodigoError.CAMPO_OBLIGATORIO_FALTANTE,
        CodigoError.FECHA_HORA_INVALIDA,
        CodigoError.FORMATO_INVALIDO,
        CodigoError.SOLICITUD_INVALIDA,
    )
    codes = {code for code, _ in descriptions}
    code = next((candidate for candidate in priority if candidate in codes), CodigoError.SOLICITUD_INVALIDA)
    return responderError(request, ExcepcionAplicacion(
        400,
        code,
        "La solicitud contiene campos invalidos.",
        detalles=[detail for _, detail in descriptions],
    ))


async def manejarErrorInterno(request: Request, error: Exception):
    # No registrar str(error), cuerpos, cabeceras ni variables de la excepcion.
    logger.error(
        "Fallo no controlado tipo=%s",
        type(error).__name__,
        extra={"correlationId": getRequestCorrelationId(request)},
    )
    return responderError(request, ExcepcionAplicacion(
        500, CodigoError.ERROR_INTERNO, "Ocurrio un error interno."
    ))


async def manejarHttpException(request: Request, error: HTTPException):
    if error.status_code in (404, 405):
        # No hay codigos de enrutamiento acordados en el contrato. Los recursos
        # del dominio usan RecursoNoEncontradoError con su codigo especifico.
        return await http_exception_handler(request, error)

    publicErrors = {
        400: (400, CodigoError.SOLICITUD_INVALIDA, "La solicitud no es valida."),
        401: (401, CodigoError.NO_AUTENTICADO, "Se requiere un token de autenticacion valido."),
        403: (403, CodigoError.NO_AUTORIZADO, "No tienes autorizacion para consultar este recurso."),
        422: (400, CodigoError.SOLICITUD_INVALIDA, "La solicitud no es valida."),
        500: (500, CodigoError.ERROR_INTERNO, "Ocurrio un error interno."),
        503: (503, CodigoError.SERVICIO_DEPENDIENTE_NO_DISPONIBLE, "El servicio dependiente no esta disponible."),
        504: (503, CodigoError.SERVICIO_DEPENDIENTE_NO_DISPONIBLE, "El servicio dependiente no esta disponible."),
    }
    status, code, message = publicErrors.get(
        error.status_code, publicErrors[500]
    )
    return responderError(request, ExcepcionAplicacion(status, code, message))


def registrarManejadores(app: FastAPI) -> None:
    app.add_exception_handler(ExcepcionAplicacion, manejarExcepcionAplicacion)
    app.add_exception_handler(RequestValidationError, manejarValidacion)
    app.add_exception_handler(HTTPException, manejarHttpException)
    app.add_exception_handler(Exception, manejarErrorInterno)
