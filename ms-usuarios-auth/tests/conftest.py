"""Fixtures aisladas: ninguna prueba unitaria necesita SQL Server ni el .env real."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


TEST_JWT_SECRET = "secreto-ficticio-exclusivo-pruebas-1234567890"
TEST_PASSWORD = "Password-Ficticio-123!"
TEST_ENV = {
    "SERVER_PORT": 8081,
    "DB_HOST": "sqlserver-ficticio.invalid",
    "DB_PORT": 1433,
    "DB_NAME": "unirride_usuarios_pruebas",
    "DB_USER": "usuario_ficticio",
    "DB_PASSWORD": "password-ficticio-solo-pruebas",
    "DB_DRIVER": "ODBC Driver 18 for SQL Server",
    "JWT_SECRET": TEST_JWT_SECRET,
    "JWT_EXPIRES_IN_SECONDS": 3600,
}


@pytest.fixture
def testSettings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    # Importar la definición no carga configuración ni conecta a la base.
    from app.config import settings as settingsModule

    settingsClass = settingsModule.Settings
    settings = settingsClass(_env_file=None, **TEST_ENV)
    # Primar el caché sin permitir que getSettings() lea un .env del desarrollador.
    # Restaurar la clase antes de importar dependencias conserva sus anotaciones.
    settingsModule.getSettings.cache_clear()
    with monkeypatch.context() as settingsPatch:
        settingsPatch.setattr(settingsModule, "Settings", lambda: settings)
        settingsModule.getSettings()
    yield settings
    settingsModule.getSettings.cache_clear()


@pytest.fixture
def dbSession(testSettings: Any) -> Iterator[Session]:
    from app.config.database import Base
    from app.models.conductor import Conductor  # noqa: F401

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"dbo": None}},
    )
    # create_all se usa exclusivamente para la base efímera de pruebas.
    # SQL Server productivo se administra siempre mediante Alembic.
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def application(testSettings: Any, dbSession: Session) -> Iterator[Any]:
    from app.config.database import getSession
    from app.config.settings import getSettings
    from app.main import createApp

    app = createApp()

    def overrideSession() -> Iterator[Session]:
        yield dbSession

    app.dependency_overrides[getSettings] = lambda: testSettings
    app.dependency_overrides[getSession] = overrideSession
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(application: Any) -> Iterator[TestClient]:
    with TestClient(application, raise_server_exceptions=False) as testClient:
        yield testClient


@pytest.fixture
def registroPayload() -> dict[str, Any]:
    return {
        "nombre": "Juan Apache",
        "correo": "juan@example.com",
        "password": TEST_PASSWORD,
        "telefono": "3001234567",
    }


@pytest.fixture
def conductorRegistrado(client: TestClient, registroPayload: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def autenticacion(
    client: TestClient,
    conductorRegistrado: dict[str, Any],
    registroPayload: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/login",
        json={"correo": registroPayload["correo"], "password": registroPayload["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def authHeaders(autenticacion: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {autenticacion['accessToken']}"}
