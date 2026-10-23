"""Respuestas uniformes sin incluir inputs, consultas SQL ni secretos."""

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
        exc.status,
        exc.error,
        getattr(request.state, "correlationId", "sin-asignar"),
    )
    return errorResponse(
        request, exc.status, exc.error, exc.message, exc.detalles, exc.headers
    )


def validationDetail(validationError: dict) -> dict[str, str]:
    """Nunca serializar input/ctx/msg: pueden contener una contraseña."""
    location = validationError.get("loc", ())
    allowedFields = {"nombre", "correo", "password", "telefono", "conductorId"}
    field = next((str(part) for part in location if part in allowedFields), "solicitud")
    errorType = validationError.get("type", "")
    if errorType == "missing":
        problem = "Campo obligatorio."
    elif errorType == "extra_forbidden":
        problem = "La solicitud contiene un campo no permitido."
    elif field == "password" and errorType in {"too_short", "string_too_short"}:
        minimumLength = validationError.get("ctx", {}).get("min_length")
        problem = (
            "Debe contener mínimo 8 caracteres."
            if minimumLength == 8
            else "La contraseña no puede estar vacía."
        )
    elif errorType == "json_invalid":
        problem = "El cuerpo debe ser JSON válido."
    elif field == "correo":
        problem = "Debe ser un correo válido de hasta 254 caracteres."
    elif field == "nombre":
        problem = "Debe contener entre 1 y 150 caracteres y no estar vacío."
    elif field == "telefono":
        problem = "Debe ser null o texto no vacío de hasta 30 caracteres."
    elif field == "conductorId":
        problem = "Debe ser un entero positivo válido para SQL Server INT."
    else:
        problem = "El valor no cumple el formato permitido."
    return {"campo": field, "problema": problem}


async def validationExceptionHandler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    types = {item.get("type", "") for item in errors}
    if "missing" in types:
        code = "CAMPO_OBLIGATORIO_FALTANTE"
    elif types.intersection(
        {"json_invalid", "int_parsing", "int_type", "string_type", "model_attributes_type"}
    ) or any(item.get("loc", ())[-1:] == ("correo",) for item in errors):
        code = "FORMATO_INVALIDO"
    else:
        code = "SOLICITUD_INVALIDA"
    logger.warning(
        "Validación rechazada error=%s correlationId=%s",
        code,
        getattr(request.state, "correlationId", "sin-asignar"),
    )
    return errorResponse(
        request,
        400,
        code,
        "Los datos de la solicitud no son válidos.",
        [validationDetail(item) for item in errors],
    )


async def httpExceptionHandler(request: Request, exc: HTTPException) -> JSONResponse:
    codes = {
        400: "SOLICITUD_INVALIDA",
        401: "NO_AUTENTICADO",
        403: "NO_AUTORIZADO",
        404: "CONDUCTOR_NO_ENCONTRADO",
        405: "SOLICITUD_INVALIDA",
    }
    messages = {
        400: "Los datos de la solicitud no son válidos.",
        401: "Se requiere un token Bearer válido.",
        403: "No está autorizado para acceder a este recurso.",
        404: "No existe el recurso solicitado.",
        405: "El método HTTP no está permitido para este recurso.",
    }
    logger.warning(
        "Error HTTP status=%s correlationId=%s",
        exc.status_code,
        getattr(request.state, "correlationId", "sin-asignar"),
    )
    return errorResponse(
        request,
        exc.status_code,
        codes.get(exc.status_code, "ERROR_INTERNO"),
        messages.get(exc.status_code, "No fue posible procesar la solicitud."),
        headers=exc.headers,
    )


async def unexpectedExceptionHandler(request: Request, exc: Exception) -> JSONResponse:
    # No traceback ni str(exc): las excepciones del driver pueden contener credenciales.
    logger.error(
        "Fallo interno tipo=%s correlationId=%s",
        type(exc).__name__,
        getattr(request.state, "correlationId", "sin-asignar"),
    )
    return errorResponse(
        request, 500, "ERROR_INTERNO", "Ocurrió un error interno al procesar la solicitud."
    )


def registerExceptionHandlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, appExceptionHandler)
    app.add_exception_handler(RequestValidationError, validationExceptionHandler)
    app.add_exception_handler(HTTPException, httpExceptionHandler)
    app.add_exception_handler(Exception, unexpectedExceptionHandler)
