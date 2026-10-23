"""Integración opcional de solo lectura; nunca crea ni modifica bases o tablas."""

import os

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.integration_db
@pytest.mark.skipif(
    os.environ.get("RUN_SQLSERVER_TESTS") != "1",
    reason="Integración SQL Server requiere RUN_SQLSERVER_TESTS=1 y configuración explícita de entorno.",
)
def test_conexion_sqlserver_y_esquema_contractual() -> None:
    from app.config.settings import Settings

    # Solo variables de entorno explícitas: nunca leer el .env del desarrollador.
    settings = Settings(_env_file=None)
    from app.config.database import buildDatabaseUrl

    engine = create_engine(buildDatabaseUrl(settings))
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
        inspector = inspect(engine)
        assert inspector.has_table("conductores", schema="dbo")
        columns = {column["name"]: column for column in inspector.get_columns("conductores", schema="dbo")}
        assert columns.keys() == {
            "id", "nombre", "correo", "password_hash", "telefono", "activo", "fecha_creacion", "fecha_actualizacion"
        }
        assert columns["nombre"]["nullable"] is False
        assert columns["correo"]["nullable"] is False
        assert columns["telefono"]["nullable"] is True
        assert columns["nombre"]["type"].length == 150
        assert columns["correo"]["type"].length == 254
        assert columns["password_hash"]["type"].length == 255
        assert columns["telefono"]["type"].length == 30
        uniqueColumns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("conductores", schema="dbo")
        }
        assert ("correo",) in uniqueColumns
    finally:
        engine.dispose()
