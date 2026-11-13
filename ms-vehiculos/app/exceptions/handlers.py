"""Manejador global de errores con el formato único del contrato."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.exceptions.exceptions import AppException
from app.schemas.error_schema import ErrorResponse

logger = logging.getLogger("uniride.errors")

CAMPOS_PERMITIDOS = {
    "placa", "marca", "modelo", "color", "tipo", "capacidad",
    "conductorId", "vehiculoId",
}


def errorResponse(
    request: Request,
    status: int,
    error: str,
    message: str,
    detalles: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    correlationId = getattr(request.state, "correlationId", None) or str(uuid4())
    request.state.correlationId = correlationId
    payload = ErrorResponse(
        timestamp=datetime.now(timezone.utc),
        status=status,
        error=error,
        message=message,
        path=request.url.path,
        correlationId=correlationId,
        detalles=(detalles or []) if status == 400 else None,
    )
    responseHeaders = dict(headers or {})
    responseHeaders["X-Correlation-Id"] = correlationId
    return JSONResponse(
        status_code=status,
        content=payload.model_dump(mode="json", exclude_none=True),
        headers=responseHeaders,
    )


async def appExceptionHandler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        "Solicitud rechazada status=%s error=%s correlationId=%s",
        exc.status, exc.error, getattr(request.state, "correlationId", "sin-asignar"),
    )
    return errorResponse(request, exc.status, exc.error, exc.message, exc.detalles, exc.headers)


def detalleValidacion(item: dict) -> dict[str, str]:
    """Nunca se devuelve el valor recibido, solo el campo y el problema."""
    campo = next(
        (str(parte) for parte in item.get("loc", ()) if parte in CAMPOS_PERMITIDOS),
        "solicitud",
    )
    tipo = item.get("type", "")
    if tipo == "missing":
        problema = "Campo obligatorio."
    elif tipo == "extra_forbidden":
        problema = "La solicitud contiene un campo no permitido."
    elif tipo == "json_invalid":
        problema = "El cuerpo debe ser JSON válido."
    elif campo == "capacidad":
        problema = "Debe ser un entero mayor o igual a 1."
    elif campo in {"conductorId", "vehiculoId"}:
        problema = "Debe ser un entero positivo."
    elif tipo == "string_too_long":
        problema = "Supera la longitud máxima permitida."
    elif tipo == "string_too_short":
        problema = "No puede estar vacío."
    elif tipo in {"string_type", "string_sub_type"}:
        problema = "Debe ser un texto."
    else:
        problema = "El valor no cumple el formato permitido."
    return {"campo": campo, "problema": problema}


async def validationExceptionHandler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errores = exc.errors()
    tipos = {item.get("type", "") for item in errores}
    campos = {detalleValidacion(item)["campo"] for item in errores}
    if "missing" in tipos:
        codigo = "CAMPO_OBLIGATORIO_FALTANTE"
    elif "capacidad" in campos:
        codigo = "CAPACIDAD_INVALIDA"
    elif tipos & {"json_invalid", "int_parsing", "int_type", "string_type",
                  "model_attributes_type", "int_from_float"}:
        codigo = "FORMATO_INVALIDO"
    else:
        codigo = "SOLICITUD_INVALIDA"
    logger.warning(
        "Validación rechazada error=%s correlationId=%s",
        codigo, getattr(request.state, "correlationId", "sin-asignar"),
    )
    return errorResponse(
        request, 400, codigo, "Los datos de la solicitud no son válidos.",
        [detalleValidacion(item) for item in errores],
    )


async def httpExceptionHandler(request: Request, exc: HTTPException) -> JSONResponse:
    codigos = {
        400: "SOLICITUD_INVALIDA",
        401: "NO_AUTENTICADO",
        403: "NO_AUTORIZADO",
        404: "VEHICULO_NO_ENCONTRADO",
        405: "SOLICITUD_INVALIDA",
    }
    mensajes = {
        400: "Los datos de la solicitud no son válidos.",
        401: "Se requiere un token Bearer válido.",
        403: "No está autorizado para acceder a este recurso.",
        404: "No existe el recurso solicitado.",
        405: "El método HTTP no está permitido para este recurso.",
    }
    return errorResponse(
        request,
        exc.status_code,
        codigos.get(exc.status_code, "ERROR_INTERNO"),
        mensajes.get(exc.status_code, "No fue posible procesar la solicitud."),
        headers=exc.headers,
    )


async def unexpectedExceptionHandler(request: Request, exc: Exception) -> JSONResponse:
    # Sin traceback ni str(exc): el driver puede incluir credenciales.
    logger.error(
        "Fallo interno tipo=%s correlationId=%s",
        type(exc).__name__, getattr(request.state, "correlationId", "sin-asignar"),
    )
    return errorResponse(
        request, 500, "ERROR_INTERNO", "Ocurrió un error interno al procesar la solicitud."
    )


def registerExceptionHandlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, appExceptionHandler)
    app.add_exception_handler(RequestValidationError, validationExceptionHandler)
    app.add_exception_handler(HTTPException, httpExceptionHandler)
    app.add_exception_handler(Exception, unexpectedExceptionHandler)
