import os

os.environ.update(
    SERVER_PORT="8082",
    DB_HOST="localhost",
    DB_PORT="5432",
    DB_NAME="unirride_vehiculos",
    DB_USER="uniride",
    DB_PASSWORD="prueba",
    JWT_SECRET="secreto-de-pruebas-con-mas-de-32-bytes!!",
)

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.dependencies import getRepository
from app.exceptions.exceptions import AppException
from app.main import app


class RepositorioEnMemoria:
    """Reemplaza a PostgreSQL con el mismo comportamiento observable."""

    def __init__(self):
        self.filas = {}
        self.siguiente = 1

    def crear(self, conductorId, datos):
        if any(f["placa"] == datos["placa"] for f in self.filas.values()):
            raise AppException(409, "PLACA_YA_REGISTRADA", "Placa repetida.")
        fila = {"id": self.siguiente, "conductor_id": conductorId, "estado": "ACTIVO", **datos}
        self.filas[self.siguiente] = fila
        self.siguiente += 1
        return dict(fila)

    def listarPorConductor(self, conductorId):
        return [dict(f) for f in self.filas.values() if f["conductor_id"] == conductorId]

    def obtener(self, vehiculoId):
        fila = self.filas.get(vehiculoId)
        return dict(fila) if fila else None

    def actualizar(self, vehiculoId, datos):
        fila = self.filas.get(vehiculoId)
        if fila is None:
            return None
        if any(f["placa"] == datos["placa"] and f["id"] != vehiculoId for f in self.filas.values()):
            raise AppException(409, "PLACA_YA_REGISTRADA", "Placa repetida.")
        fila.update(datos)
        return dict(fila)

    def darDeBaja(self, vehiculoId):
        self.filas[vehiculoId]["estado"] = "INACTIVO"


@pytest.fixture
def cliente():
    repo = RepositorioEnMemoria()
    app.dependency_overrides[getRepository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def tokenDe(conductorId, vigenciaSegundos=3600):
    ahora = int(time.time())
    return jwt.encode(
        {"sub": str(conductorId), "iat": ahora, "exp": ahora + vigenciaSegundos},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )


def cabeceras(conductorId):
    return {"Authorization": f"Bearer {tokenDe(conductorId)}"}


VEHICULO = {
    "placa": "abc123", "marca": "Renault", "modelo": "Logan",
    "color": "Gris", "tipo": "Automovil", "capacidad": 4,
}
