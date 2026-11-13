"""Errores funcionales independientes de FastAPI y del driver de base de datos."""


class AppException(Exception):
    def __init__(
        self,
        status: int,
        error: str,
        message: str,
        detalles: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message
        self.detalles = detalles
        self.headers = headers or {}
