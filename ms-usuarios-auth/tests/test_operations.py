"""Regresiones del arranque LAN y de las comprobaciones públicas de salud."""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.orm import Session

from tests.conftest import TEST_ENV


def test_launcher_escucha_en_lan_por_defecto(testSettings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import __main__ as launcher

    launches = []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda *args, **kwargs: launches.append((args, kwargs)))
    launcher.main()
    assert launches[0][1]["host"] == "0.0.0.0"
    assert launches[0][1]["port"] == testSettings.SERVER_PORT


def test_launcher_respeta_interfaz_configurada(testSettings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import __main__ as launcher

    configured = testSettings.model_copy(update={"SERVER_HOST": "25.32.113.17"})
    monkeypatch.setattr(launcher, "getSettings", lambda: configured)
    launches = []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda *args, **kwargs: launches.append((args, kwargs)))
    launcher.main()
    assert launches[0][1]["host"] == "25.32.113.17"


def test_interfaz_vacia_no_es_valida() -> None:
    from app.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, SERVER_HOST=" ", **TEST_ENV)


def test_health_publico_no_abre_conexion(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.controllers import health_controller

    def unexpectedDatabaseAccess() -> None:
        raise AssertionError("Liveness no debe abrir SQL Server.")

    monkeypatch.setattr(health_controller, "getEngine", unexpectedDatabaseAccess)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP", "servicio": "ms-usuarios-auth"}


def test_readiness_publico_consulta_db(
    client: TestClient, dbSession: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.controllers import health_controller

    engine = dbSession.get_bind()
    statements = []

    def recordStatement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", recordStatement)
    monkeypatch.setattr(health_controller, "getEngine", lambda: engine)
    try:
        response = client.get("/health/ready")
    finally:
        event.remove(engine, "before_cursor_execute", recordStatement)
    assert response.status_code == 200
    assert response.json() == {"status": "UP", "servicio": "ms-usuarios-auth", "database": "UP"}
    assert statements == ["SELECT 1"]


@pytest.mark.parametrize("failureSource", ["engine", "connection", "query"])
def test_readiness_fallido_no_expone_driver_ni_secretos(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture, failureSource: str,
) -> None:
    from app.controllers import health_controller

    def unavailable(*args) -> None:
        raise RuntimeError("ODBC password=secreto-ficticio-no-publicar")

    @contextmanager
    def connect():
        if failureSource == "connection":
            unavailable()
        yield SimpleNamespace(execute=unavailable)

    getEngine = unavailable if failureSource == "engine" else lambda: SimpleNamespace(connect=connect)
    monkeypatch.setattr(health_controller, "getEngine", getEngine)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "DOWN", "servicio": "ms-usuarios-auth", "database": "DOWN"}
    assert "secreto-ficticio-no-publicar" not in response.text + caplog.text
