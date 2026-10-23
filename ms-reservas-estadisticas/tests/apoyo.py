"""Sistema completo en memoria: API real, clientes reales y mocks ASGI."""

from contextlib import contextmanager
import secrets
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import httpx
import jwt
from pydantic import SecretStr

from app.clients.vehiculos_client import VehiculosClient, getVehiculosClient
from app.clients.viajes_client import ViajesClient, getViajesClient
from app.config.settings import HttpClientSettings
from app.main import crearAplicacion
from app.repositories.reserva_repository import getReservaRepository
from app.security.jwt_service import JwtService, getJwtService
from mocks.common import getServiceApiKey
from mocks.vehiculos_mock import crearVehiculosMock
from mocks.viajes_mock import crearViajesMock
from scripts.verificar_reservas_viaje import RepositorioSimulado


class RepositorioMemoria(RepositorioSimulado):
    def obtenerPorId(self, reservaId):
        self.eventos.append("detalle")
        if self.fallo is not None:
            raise self.fallo
        return next((r for r in self.datos if r.id == reservaId), None)

    def resumirPorViajes(self, viajeIds):
        self.eventos.append("resumen")
        return super().resumirPorViajes(viajeIds)


class TransporteLocal(httpx.AsyncBaseTransport):
    def __init__(self, viajes, vehiculos):
        self.requests = []
        self.fallos = {}
        self.transportes = {
            "viajes.test": httpx.ASGITransport(app=viajes),
            "vehiculos.test": httpx.ASGITransport(app=vehiculos),
        }

    async def handle_async_request(self, request):
        self.requests.append(request)
        fallo = self.fallos.get((request.url.host, request.method))
        if fallo == "timeout":
            raise httpx.ReadTimeout("Fallo simulado", request=request)
        if fallo == "caido":
            return httpx.Response(503, json={"detail": "Fallo simulado"}, request=request)
        if fallo == "invalido":
            return httpx.Response(200, json={"viajeId": "invalido"}, request=request)
        return await self.transportes[request.url.host].handle_async_request(request)


@contextmanager
def sistema(repository=None):
    secreto = SecretStr(secrets.token_urlsafe(64))
    llave = SecretStr(secrets.token_urlsafe(64))
    autenticacion = JwtService(secreto)
    viajes = crearViajesMock()
    vehiculos = crearVehiculosMock()
    app = crearAplicacion()
    for application in (viajes, vehiculos, app):
        application.dependency_overrides[getJwtService] = lambda: autenticacion
    viajes.dependency_overrides[getServiceApiKey] = lambda: llave
    eventos = []
    repository = repository if repository is not None else RepositorioMemoria(eventos)
    app.dependency_overrides[getReservaRepository] = lambda: repository
    transporte = TransporteLocal(viajes, vehiculos)
    settings = HttpClientSettings(
        _env_file=None, VIAJES_SERVICE_URL="http://viajes.test",
        VEHICULOS_SERVICE_URL="http://vehiculos.test", HTTP_TIMEOUT_MS=3000,
        HTTP_MAX_RETRIES=1,
    )

    async def proveedorViajes():
        async with httpx.AsyncClient(transport=transporte, trust_env=False) as http:
            yield ViajesClient(settings, http, llave)

    async def proveedorVehiculos():
        async with httpx.AsyncClient(transport=transporte, trust_env=False) as http:
            yield VehiculosClient(settings, http)

    app.dependency_overrides[getViajesClient] = proveedorViajes
    app.dependency_overrides[getVehiculosClient] = proveedorVehiculos

    def headers(conductorId=25, modo="valido", correlationId=None):
        if modo == "ausente":
            return {}
        ahora = int(time.time())
        token = jwt.encode(
            {"sub": str(conductorId), "iat": ahora - 60,
             "exp": ahora - 1 if modo == "vencido" else ahora + 3600},
            secrets.token_urlsafe(64) if modo == "otra_firma" else secreto.get_secret_value(),
            algorithm="HS256",
        )
        resultado = {"Authorization": "Bearer " + ("invalido" if modo == "invalido" else token)}
        if correlationId is not None:
            resultado["X-Correlation-Id"] = correlationId
        return resultado

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, headers=headers, repository=repository,
            transporte=transporte, viajes=viajes, vehiculos=vehiculos,
            secreto=secreto, llave=llave, eventos=eventos,
        )
