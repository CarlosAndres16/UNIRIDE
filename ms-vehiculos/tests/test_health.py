from contextlib import contextmanager
from importlib import import_module
import runpy

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


main = import_module("app.main")


def test_health_responde_sin_token_y_sin_acceder_a_postgresql(cliente, monkeypatch):
    def conexion_no_permitida(*args):
        pytest.fail("Liveness no debe depender de PostgreSQL.")

    monkeypatch.setattr(main, "abrirConexion", conexion_no_permitida)
    response = cliente.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP", "servicio": "ms-vehiculos"}


def test_ready_consulta_postgresql_sin_token(cliente, monkeypatch):
    consultas = []

    class Cursor:
        def execute(self, sql):
            consultas.append(sql)

        def fetchone(self):
            return {"?column?": 1}

    class Conexion:
        @contextmanager
        def cursor(self):
            yield Cursor()

    @contextmanager
    def conexion(settings):
        yield Conexion()

    monkeypatch.setattr(main, "abrirConexion", conexion)
    response = cliente.get("/health/ready")
    assert consultas == ["SELECT 1"]
    assert response.status_code == 200
    assert response.json() == {"status": "UP", "servicio": "ms-vehiculos", "database": "UP"}


@pytest.mark.parametrize("falla_en", ["configuracion", "conexion", "consulta"])
def test_ready_fallido_devuelve_503_sin_detalles_privados(cliente, monkeypatch, caplog, falla_en):
    secreto = "credencial-privada-de-prueba"

    def falla(*args):
        raise RuntimeError(secreto)

    if falla_en == "configuracion":
        monkeypatch.setattr(main, "getSettings", falla)
    elif falla_en == "conexion":
        monkeypatch.setattr(main, "abrirConexion", falla)
    else:
        class Cursor:
            execute = falla

        class Conexion:
            @contextmanager
            def cursor(self):
                yield Cursor()

        @contextmanager
        def conexion(settings):
            yield Conexion()

        monkeypatch.setattr(main, "abrirConexion", conexion)

    response = cliente.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "DOWN", "servicio": "ms-vehiculos", "database": "DOWN"}
    assert secreto not in response.text
    assert secreto not in caplog.text


def test_arranque_respeta_host_configurado(monkeypatch):
    import uvicorn

    llamadas = []
    monkeypatch.setenv("SERVER_HOST", "25.0.88.33")
    monkeypatch.setattr("app.config.settings.getSettings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: llamadas.append((args, kwargs)))
    runpy.run_module("app", run_name="__main__")
    assert llamadas == [(("app.main:app",), {"host": "25.0.88.33", "port": 8082})]


def test_host_por_defecto_permite_lan(monkeypatch):
    monkeypatch.delenv("SERVER_HOST", raising=False)
    assert Settings(_env_file=None).SERVER_HOST == "0.0.0.0"


def test_host_rechaza_espacios_y_normaliza_valor():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SERVER_HOST="   ")
    assert Settings(_env_file=None, SERVER_HOST=" 25.0.88.33 ").SERVER_HOST == "25.0.88.33"
