"""El diagnóstico no abre SQL en las pruebas ni revela fallos del proveedor."""
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.controllers.health_controller import databaseReady
from app.main import crearAplicacion


def test_health_independiente_de_sql():
    with patch("app.controllers.health_controller.getEngine", side_effect=AssertionError("SQL no permitido")):
        with TestClient(crearAplicacion()) as client:
            response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP", "servicio": "ms-reservas-estadisticas"}


def test_readiness_disponible_y_caida():
    app = crearAplicacion()
    for available, expected in [(True, 200), (False, 503)]:
        app.dependency_overrides[databaseReady] = lambda: available
        with TestClient(app) as client:
            response = client.get("/health/ready")
        assert response.status_code == expected
        assert response.json()["database"] == ("UP" if available else "DOWN")


def test_error_odbc_no_se_expone():
    with patch("app.controllers.health_controller.getEngine", side_effect=RuntimeError("credencial-privada")):
        with TestClient(crearAplicacion()) as client:
            response = client.get("/health/ready")
    assert response.status_code == 503
    assert "credencial-privada" not in response.text
