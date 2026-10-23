"""Logs de la aplicacion en UTC, con identificador de solicitud."""

import logging
import time

from app.middleware.correlation_id import getCorrelationId


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "correlationId", None):
            record.correlationId = getCorrelationId() or "-"
        return True


def configurarLogging() -> None:
    """Configura una sola salida, incluso al crear varias apps de prueba."""

    logger = logging.getLogger("uniride")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(getattr(handler, "unirideHandler", False) for handler in logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.unirideHandler = True
    handler.addFilter(CorrelationIdFilter())
    formatter = logging.Formatter(
        "%(asctime)sZ level=%(levelname)s correlationId=%(correlationId)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)
