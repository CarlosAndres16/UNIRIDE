"""Conexión PostgreSQL diferida: importar la app no abre conexiones."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config.settings import Settings


@contextmanager
def abrirConexion(settings: Settings) -> Iterator[psycopg.Connection]:
    with psycopg.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD.get_secret_value(),
        row_factory=dict_row,
        connect_timeout=3,
    ) as conexion:
        yield conexion
