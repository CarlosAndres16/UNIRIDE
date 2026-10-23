"""Excepciones públicas tipadas y compatibles con el contrato de errores."""

from collections.abc import Sequence

from app.schemas.error_schema import CodigoError, DetalleError, ESTADO_POR_CODIGO


class ExcepcionAplicacion(Exception):
    """Contiene únicamente datos públicos que el manejador puede responder."""

    status: int
    error: CodigoError
    message: str
    detalles: list[DetalleError] | None

    def __init__(
        self,
        status: int,
        error: CodigoError | str,
        message: str,
        detalles: Sequence[DetalleError | dict[str, str]] | None = None,
    ) -> None:
        if not isinstance(status, int) or isinstance(status, bool):
            raise ValueError("El estado HTTP debe ser un entero del contrato.")
        try:
            codigo = CodigoError(error)
        except (TypeError, ValueError):
            raise ValueError("El código de error debe pertenecer al contrato.") from None
        if ESTADO_POR_CODIGO[codigo] != status:
            raise ValueError("El código de error no corresponde al estado HTTP.")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("El mensaje público debe ser un texto no vacío.")
        if detalles is not None and status != 400:
            raise ValueError("Los detalles de validación solo se permiten en errores 400.")

        self.status = status
        self.error = codigo
        self.message = message
        if status == 400:
            self.detalles = (
                [DetalleError.model_validate(detalle) for detalle in detalles]
                if detalles is not None
                else []
            )
        else:
            self.detalles = None
        super().__init__(message)


class SolicitudInvalidaError(ExcepcionAplicacion):
    def __init__(
        self,
        message: str = "La solicitud no es válida.",
        detalles: Sequence[DetalleError | dict[str, str]] | None = None,
        error: CodigoError = CodigoError.SOLICITUD_INVALIDA,
    ) -> None:
        super().__init__(400, error, message, detalles)


class NoAutenticadoError(ExcepcionAplicacion):
    def __init__(self, message: str = "Se requiere un token de autenticación válido.") -> None:
        super().__init__(401, CodigoError.NO_AUTENTICADO, message)


class NoAutorizadoError(ExcepcionAplicacion):
    def __init__(self, message: str = "No tienes autorización para consultar este recurso.") -> None:
        super().__init__(403, CodigoError.NO_AUTORIZADO, message)


class RecursoNoEncontradoError(ExcepcionAplicacion):
    def __init__(self, error: CodigoError, message: str) -> None:
        super().__init__(404, error, message)


class ErrorInterno(ExcepcionAplicacion):
    def __init__(self, message: str = "Ocurrió un error interno.") -> None:
        super().__init__(500, CodigoError.ERROR_INTERNO, message)


class ServicioDependienteNoDisponibleError(ExcepcionAplicacion):
    def __init__(self, message: str = "El servicio dependiente no está disponible.") -> None:
        super().__init__(503, CodigoError.SERVICIO_DEPENDIENTE_NO_DISPONIBLE, message)
