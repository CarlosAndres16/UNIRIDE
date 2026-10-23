"""Pruebas asíncronas de clientes REST con transportes HTTP en memoria."""

from tests.contrato import RUTAS_CONTRATO

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, date, datetime
import json
import logging
import os
import secrets
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import jwt
from pydantic import SecretStr, ValidationError

from app.clients.viajes_client import ViajesClient, getViajesClient
from app.clients.vehiculos_client import VehiculosClient, getVehiculosClient
from app.config.settings import HttpClientSettings
from app.exceptions.exceptions import ExcepcionAplicacion
from app.main import app as aplicacionProduccion, crearAplicacion
from app.schemas.integracion_schema import ListaViajesExterna, VehiculoExterno, ViajeExterno
from app.security.jwt_service import ConductorAutenticado, JwtService, getJwtService
from mocks.common import getServiceApiKey
from mocks.data import crearVehiculosEjemplo, crearViajesEjemplo
from mocks.vehiculos_mock import crearVehiculosMock
from mocks.viajes_mock import crearViajesMock

ASYNC_CLIENT_CLASS = httpx.AsyncClient
DATO_PRIVADO = "DATO_PRIVADO_HTTP_NO_PUBLICAR_56EAF4"
CABECERA_PRIVADA = "CABECERA_PRIVADA_HTTP_NO_PUBLICAR_8F27C1"
CODIGO_NO_DISPONIBLE = "SERVICIO_DEPENDIENTE_NO_DISPONIBLE"


class CapturaLogs(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.registros: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.registros.append(record)


@contextmanager
def capturarLogs():
    logger = logging.getLogger("uniride")
    captura = CapturaLogs()
    logger.addHandler(captura)
    try:
        yield captura
    finally:
        logger.removeHandler(captura)
        captura.close()


class TransportMocks(httpx.AsyncBaseTransport):
    """Enruta por host a aplicaciones ASGI; nunca abre sockets externos."""

    def __init__(self, viajesApp, vehiculosApp) -> None:
        self.requests: list[httpx.Request] = []
        self.transports = {
            "viajes.test": httpx.ASGITransport(app=viajesApp, raise_app_exceptions=True),
            "vehiculos.test": httpx.ASGITransport(app=vehiculosApp, raise_app_exceptions=True),
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self.transports[request.url.host].handle_async_request(request)

    async def aclose(self) -> None:
        for transport in self.transports.values():
            await transport.aclose()


class VerificacionClientes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.configuracion = {
            "VIAJES_SERVICE_URL": "http://viajes.test",
            "VEHICULOS_SERVICE_URL": "http://vehiculos.test",
            "HTTP_TIMEOUT_MS": 3000,
            "HTTP_MAX_RETRIES": 1,
        }
        self.settings = HttpClientSettings(_env_file=None, **self.configuracion)
        self.secret = SecretStr(secrets.token_urlsafe(64))
        self.serviceKey = SecretStr(secrets.token_urlsafe(64))
        ahora = int(time.time())
        token = jwt.encode(
            {"sub": "25", "iat": ahora - 5, "exp": ahora + 3600},
            self.secret.get_secret_value(),
            algorithm="HS256",
        )
        self.conductor = ConductorAutenticado(25, SecretStr(token))
        self.correlationId = str(uuid4())
        self.viajesDatos = [viaje.model_dump(mode="json") for viaje in crearViajesEjemplo()]
        self.vehiculosDatos = [vehiculo.model_dump(mode="json") for vehiculo in crearVehiculosEjemplo()]
        self.viaje = deepcopy(next(viaje for viaje in self.viajesDatos if viaje["viajeId"] == 305))
        self.vehiculo = deepcopy(next(vehiculo for vehiculo in self.vehiculosDatos if vehiculo["vehiculoId"] == 12))

    async def crearHttp(self, responder, **kwargs) -> httpx.AsyncClient:
        return await self.enterAsyncContext(ASYNC_CLIENT_CLASS(
            transport=httpx.MockTransport(responder), trust_env=False, **kwargs
        ))

    def ocupacion(self, total: int = 3) -> dict:
        return {
            "viajeId": 305, "capacidad": 4, "cuposDisponibles": 4 - total,
            "estado": "ACTIVO", "version": 2, "fechaActualizacion": "2026-10-22T12:00:00Z",
        }

    def pagina(self, datos: list[dict] | None = None, *, pagina: int = 1, total: int | None = None) -> dict:
        datos = [deepcopy(self.viaje)] if datos is None else deepcopy(datos)
        total = len(datos) if total is None else total
        return {
            "datos": datos,
            "paginacion": {
                "pagina": pagina, "tamano": 50, "totalElementos": total,
                "totalPaginas": (total + 49) // 50,
            },
        }

    def errorProveedor(self, request: httpx.Request, status: int, codigo: str) -> dict:
        body = {
            "timestamp": "2026-10-22T12:00:00Z", "status": status, "error": codigo,
            "message": DATO_PRIVADO, "path": request.url.path,
            "correlationId": request.headers.get("X-Correlation-Id", self.correlationId),
        }
        if status == 400:
            body["detalles"] = [{"campo": "dato", "problema": DATO_PRIVADO}]
        return body

    async def esperarError(self, operation, status: int = 503, codigo: str = CODIGO_NO_DISPONIBLE):
        with self.assertRaises(ExcepcionAplicacion) as raised:
            await operation
        error = raised.exception
        self.assertEqual(error.status, status)
        self.assertEqual(error.error.value, codigo)
        publicos = str(error) + repr(error.detalles)
        for privado in (DATO_PRIVADO, CABECERA_PRIVADA, self.secret.get_secret_value(), self.serviceKey.get_secret_value(), self.conductor.token.get_secret_value()):
            self.assertNotIn(privado, publicos)
        return error

    async def test_settings_http_independientes_y_valores_explicitos(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = HttpClientSettings(_env_file=None, **self.configuracion)
        self.assertEqual(str(settings.viajesServiceUrl), "http://viajes.test/")
        self.assertEqual(str(settings.vehiculosServiceUrl), "http://vehiculos.test/")
        self.assertEqual(settings.httpTimeoutMs, 3000)
        self.assertEqual(settings.httpMaxRetries, 1)

    async def test_settings_rechazan_urls_ausentes_credenciales_y_retry_mayor_a_uno(self) -> None:
        casos = []
        for campo in ("VIAJES_SERVICE_URL", "VEHICULOS_SERVICE_URL"):
            caso = dict(self.configuracion)
            caso.pop(campo)
            casos.append(caso)
            for value in ("", "ftp://proveedor.test", "http://usuario:" + DATO_PRIVADO + "@proveedor.test", "http://proveedor.test/ruta", "http://proveedor.test?dato=" + DATO_PRIVADO):
                casos.append(self.configuracion | {campo: value})
        casos.extend((self.configuracion | {"HTTP_MAX_RETRIES": 2}, self.configuracion | {"HTTP_TIMEOUT_MS": 0}))
        with patch.dict(os.environ, {}, clear=True):
            for indice, kwargs in enumerate(casos):
                with self.subTest(caso=indice):
                    with self.assertRaises(ValidationError) as raised:
                        HttpClientSettings(_env_file=None, **kwargs)
                    self.assertNotIn(DATO_PRIVADO, str(raised.exception))

    async def test_detalles_correctos_propagan_jwt_uuid_y_timeout_de_tres_segundos(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(200, json=self.viaje if request.url.host == "viajes.test" else self.vehiculo)
        http = await self.crearHttp(responder, timeout=60)
        viaje = await ViajesClient(self.settings, http).obtenerViaje(305, self.conductor, self.correlationId.upper())
        vehiculo = await VehiculosClient(self.settings, http).obtenerVehiculo(12, self.conductor, self.correlationId.upper())
        self.assertIsInstance(viaje, ViajeExterno)
        self.assertIsInstance(vehiculo, VehiculoExterno)
        self.assertEqual(viaje.viajeId, 305)
        self.assertEqual(vehiculo.vehiculoId, 12)
        self.assertEqual([request.url.path for request in requests], ["/api/v1/viajes/305", "/api/v1/vehiculos/12"])
        for request in requests:
            self.assertEqual(request.headers["Authorization"], "Bearer " + self.conductor.token.get_secret_value())
            self.assertEqual(request.headers["X-Correlation-Id"], self.correlationId)
            self.assertNotIn("X-Service-Key", request.headers)
            self.assertEqual(request.extensions["timeout"], {"connect": 3.0, "read": 3.0, "write": 3.0, "pool": 3.0})

    async def test_integracion_asgi_recupera_detalles_51_viajes_y_conserva_cancelados(self) -> None:
        viajesApp, vehiculosApp = crearViajesMock(), crearVehiculosMock()
        jwtService = JwtService(self.secret)
        for app in (viajesApp, vehiculosApp):
            app.dependency_overrides[getJwtService] = lambda: jwtService
            app.dependency_overrides[getServiceApiKey] = lambda: self.serviceKey
        transport = TransportMocks(viajesApp, vehiculosApp)
        http = await self.enterAsyncContext(ASYNC_CLIENT_CLASS(transport=transport, trust_env=False))
        viajes = ViajesClient(self.settings, http, self.serviceKey)
        vehiculos = VehiculosClient(self.settings, http)
        self.assertEqual((await viajes.obtenerViaje(305, self.conductor)).capacidad, 4)
        self.assertEqual((await vehiculos.obtenerVehiculo(12, self.conductor)).conductorId, 25)
        todos = await viajes.listarTodosLosViajes(self.conductor, conductorId=27, correlationId=self.correlationId)
        self.assertEqual([viaje.viajeId for viaje in todos], list(range(1000, 1051)))
        pages = [request for request in transport.requests if request.url.path == "/api/v1/viajes"]
        self.assertEqual([request.url.params["pagina"] for request in pages], ["1", "2"])
        self.assertTrue(all(request.headers["X-Correlation-Id"] == self.correlationId for request in pages))
        propios = await viajes.listarTodosLosViajes(self.conductor, conductorId=25)
        self.assertEqual([viaje.viajeId for viaje in propios], [305, 306, 307, 308])
        self.assertEqual(next(viaje.estado.value for viaje in propios if viaje.viajeId == 307), "CANCELADO")
        resultado = await viajes.actualizarOcupacion(305, 3, self.correlationId)
        self.assertEqual(resultado.cuposDisponibles, 1)

    async def test_listar_pagina_fuerza_todos_tamano_50_y_filtros_iso(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(200, json=self.pagina())
        http = await self.crearHttp(responder)
        pagina = await ViajesClient(self.settings, http).listarViajes(
            self.conductor, conductorId=25, vehiculoId=12, desde=date(2026, 10, 1), hasta=date(2026, 10, 31),
        )
        self.assertIsInstance(pagina, ListaViajesExterna)
        self.assertEqual(dict(requests[0].url.params), {
            "conductorId": "25", "vehiculoId": "12", "desde": "2026-10-01", "hasta": "2026-10-31",
            "estado": "TODOS", "pagina": "1", "tamano": "50",
        })

    async def test_sesion_inyectada_no_filtra_autenticacion_opuesta_ni_aplica_auth_global(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(200, json=self.ocupacion() if request.method == "PUT" else self.viaje)
        http = await self.crearHttp(
            responder, auth=("usuario-global", DATO_PRIVADO),
            headers={"Authorization": "Bearer " + DATO_PRIVADO, "X-Service-Key": CABECERA_PRIVADA},
        )
        cliente = ViajesClient(self.settings, http, self.serviceKey)
        await cliente.obtenerViaje(305, self.conductor)
        await cliente.actualizarOcupacion(305, 3)
        self.assertEqual(requests[0].headers["Authorization"], "Bearer " + self.conductor.token.get_secret_value())
        self.assertNotIn("X-Service-Key", requests[0].headers)
        self.assertNotIn("Authorization", requests[1].headers)
        self.assertEqual(requests[1].headers["X-Service-Key"], self.serviceKey.get_secret_value())

    async def test_recupera_una_falla_transitoria_con_mismo_jwt_uuid_y_un_solo_reintento(self) -> None:
        for fallo in ("timeout", "503", "dto"):
            with self.subTest(fallo=fallo):
                requests = []
                def responder(request):
                    requests.append(request)
                    if len(requests) == 1:
                        if fallo == "timeout":
                            raise httpx.ReadTimeout(DATO_PRIVADO, request=request)
                        return httpx.Response(503, text=DATO_PRIVADO) if fallo == "503" else httpx.Response(200, json={"dato": DATO_PRIVADO})
                    return httpx.Response(200, json=self.viaje)
                http = await self.crearHttp(responder)
                viaje = await ViajesClient(self.settings, http).obtenerViaje(305, self.conductor, self.correlationId.upper())
                self.assertEqual(viaje.viajeId, 305)
                self.assertEqual(len(requests), 2)
                self.assertEqual({request.headers["X-Correlation-Id"] for request in requests}, {self.correlationId})
                self.assertTrue(all(request.headers["Authorization"] == "Bearer " + self.conductor.token.get_secret_value() for request in requests))

    async def test_timeout_conexion_y_protocolo_agotados_son_503_en_dos_intentos(self) -> None:
        for tipo in (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError):
            with self.subTest(tipo=tipo.__name__):
                requests = []
                def responder(request):
                    requests.append(request)
                    raise tipo(DATO_PRIVADO, request=request)
                http = await self.crearHttp(responder)
                await self.esperarError(ViajesClient(self.settings, http).obtenerViaje(305, self.conductor))
                self.assertEqual(len(requests), 2)

    async def test_estados_5xx_agotan_dos_intentos_y_nunca_se_vuelven_404_o_504(self) -> None:
        for status in (500, 502, 503, 504):
            with self.subTest(status=status):
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(status, text=DATO_PRIVADO)
                http = await self.crearHttp(responder)
                await self.esperarError(ViajesClient(self.settings, http).obtenerViaje(305, self.conductor))
                self.assertEqual(len(requests), 2)

    async def test_200_json_y_dto_invalidos_reintentan_una_vez_y_fallan_503(self) -> None:
        variantes = [("viajes", None)]
        for campo, valor in (
            ("viajeId", "305"), ("capacidad", True), ("fechaSalida", "2026-1-01"),
            ("horaSalida", "07:00:00"), ("fechaCreacion", "2026-10-01T14:00:00"),
            ("fechaActualizacion", "1790870400"), ("fechaCreacion", 1790870400),
            ("cuposDisponibles", 5), ("privado", DATO_PRIVADO),
        ):
            variantes.append(("viajes", self.viaje | {campo: valor}))
        faltaCampo = deepcopy(self.viaje)
        faltaCampo.pop("origen")
        variantes.append(("viajes", faltaCampo))
        puntoInvalido = deepcopy(self.viaje)
        puntoInvalido["origen"]["latitud"] = "4.0"
        variantes.append(("viajes", puntoInvalido))
        for campo, valor in (("vehiculoId", True), ("capacidad", "4"), ("marca", 123), ("estado", "ELIMINADO")):
            variantes.append(("vehiculos", self.vehiculo | {campo: valor}))
        for indice, (servicio, payload) in enumerate(variantes):
            with self.subTest(caso=indice, servicio=servicio):
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(200, text=DATO_PRIVADO) if payload is None else httpx.Response(200, json=payload)
                http = await self.crearHttp(responder)
                operation = ViajesClient(self.settings, http).obtenerViaje(305, self.conductor) if servicio == "viajes" else VehiculosClient(self.settings, http).obtenerVehiculo(12, self.conductor)
                await self.esperarError(operation)
                self.assertEqual(len(requests), 2)

    async def test_400_401_403_404_validos_preservan_codigo_sin_reintento_ni_mensajes_privados(self) -> None:
        casos = (
            ("viajes", 400, "SOLICITUD_INVALIDA"), ("viajes", 401, "NO_AUTENTICADO"),
            ("viajes", 403, "NO_AUTORIZADO"), ("viajes", 404, "VIAJE_NO_ENCONTRADO"),
            ("vehiculos", 404, "VEHICULO_NO_ENCONTRADO"),
        )
        for servicio, status, codigo in casos:
            with self.subTest(servicio=servicio, status=status):
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(status, json=self.errorProveedor(request, status, codigo), headers={"X-Private": CABECERA_PRIVADA})
                http = await self.crearHttp(responder)
                operation = ViajesClient(self.settings, http).obtenerViaje(305, self.conductor) if servicio == "viajes" else VehiculosClient(self.settings, http).obtenerVehiculo(12, self.conductor)
                error = await self.esperarError(operation, status, codigo)
                self.assertEqual(error.detalles, [] if status == 400 else None)
                self.assertEqual(len(requests), 1)

    async def test_put_409_se_preserva_y_get_409_es_respuesta_invalida_sin_retry(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(409, json=self.errorProveedor(request, 409, "OPERACION_NO_PERMITIDA_POR_ESTADO"))
        http = await self.crearHttp(responder)
        cliente = ViajesClient(self.settings, http, self.serviceKey)
        await self.esperarError(cliente.actualizarOcupacion(305, 3), 409, "OPERACION_NO_PERMITIDA_POR_ESTADO")
        self.assertEqual(len(requests), 1)
        await self.esperarError(cliente.obtenerViaje(305, self.conductor))
        self.assertEqual(len(requests), 2)

    async def test_errores_4xx_con_cuerpo_invalido_son_503_sin_retry(self) -> None:
        for caso in ("json", "campo_ausente", "timestamp_ausente", "timestamp_epoch", "estado_incoherente", "recurso_incorrecto", "detalles400_ausentes", "detalles400_null", "detalles404_null"):
            with self.subTest(caso=caso):
                requests = []
                def responder(request):
                    requests.append(request)
                    status = 400 if caso.startswith("detalles400_") else 404
                    codigo = "SOLICITUD_INVALIDA" if status == 400 else "VIAJE_NO_ENCONTRADO"
                    body = self.errorProveedor(request, status, codigo)
                    if caso == "json":
                        return httpx.Response(status, text=DATO_PRIVADO)
                    if caso == "campo_ausente":
                        body.pop("correlationId")
                    elif caso == "timestamp_ausente":
                        body.pop("timestamp")
                    elif caso == "timestamp_epoch":
                        body["timestamp"] = "1790870400"
                    elif caso == "estado_incoherente":
                        body["status"] = 401
                        body["error"] = "NO_AUTENTICADO"
                    elif caso == "recurso_incorrecto":
                        body["error"] = "VEHICULO_NO_ENCONTRADO"
                    elif caso == "detalles400_ausentes":
                        body.pop("detalles")
                    elif caso in ("detalles400_null", "detalles404_null"):
                        body["detalles"] = None
                    return httpx.Response(status, json=body)
                http = await self.crearHttp(responder)
                await self.esperarError(ViajesClient(self.settings, http).obtenerViaje(305, self.conductor))
                self.assertEqual(len(requests), 1)

    async def test_redirects_y_estados_no_contractuales_no_se_siguen_ni_reintentan(self) -> None:
        for status in (201, 204, 301, 302, 303, 307, 308, 408, 422, 429):
            with self.subTest(status=status):
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(status, headers={"Location": "http://otro-proveedor.test/" + CABECERA_PRIVADA}, text=DATO_PRIVADO)
                http = await self.crearHttp(responder, follow_redirects=True)
                await self.esperarError(ViajesClient(self.settings, http).obtenerViaje(305, self.conductor))
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0].url.host, "viajes.test")

    async def test_cero_reintentos_realiza_un_solo_intento(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            raise httpx.ConnectError(DATO_PRIVADO, request=request)
        http = await self.crearHttp(responder)
        settings = HttpClientSettings(_env_file=None, **(self.configuracion | {"HTTP_MAX_RETRIES": 0}))
        await self.esperarError(ViajesClient(settings, http).obtenerViaje(305, self.conductor))
        self.assertEqual(len(requests), 1)

    async def test_deadline_real_por_intento_detiene_un_transporte_que_no_responde(self) -> None:
        requests = []
        async def responder(request):
            requests.append(request)
            await asyncio.sleep(10)
            return httpx.Response(200, json=self.viaje)
        http = await self.crearHttp(responder)
        settings = HttpClientSettings(_env_file=None, **(self.configuracion | {"HTTP_TIMEOUT_MS": 20}))
        started = time.monotonic()
        await self.esperarError(ViajesClient(settings, http).obtenerViaje(305, self.conductor))
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(len(requests), 2)

    async def test_detalle_de_otro_id_es_503_sin_reintento_adicional(self) -> None:
        for servicio, payload in (("viajes", self.viaje | {"viajeId": 306}), ("vehiculos", self.vehiculo | {"vehiculoId": 13})):
            with self.subTest(servicio=servicio):
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(200, json=payload)
                http = await self.crearHttp(responder)
                operation = ViajesClient(self.settings, http).obtenerViaje(305, self.conductor) if servicio == "viajes" else VehiculosClient(self.settings, http).obtenerVehiculo(12, self.conductor)
                await self.esperarError(operation)
                self.assertEqual(len(requests), 1)

    async def test_detalle_de_otro_propietario_es_403_sin_reintento(self) -> None:
        for servicio, payload in (("viajes", self.viaje | {"conductorId": 26}), ("vehiculos", self.vehiculo | {"conductorId": 26})):
            with self.subTest(servicio=servicio):
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(200, json=payload)
                http = await self.crearHttp(responder)
                operation = ViajesClient(self.settings, http).obtenerViaje(305, self.conductor) if servicio == "viajes" else VehiculosClient(self.settings, http).obtenerVehiculo(12, self.conductor)
                await self.esperarError(operation, 403, "NO_AUTORIZADO")
                self.assertEqual(len(requests), 1)

    async def test_metadatos_y_duplicados_en_una_pagina_incoherentes_son_503(self) -> None:
        for campo, value in (("pagina", 2), ("tamano", 20), ("totalPaginas", 2), ("totalElementos", 2), ("duplicados", None)):
            with self.subTest(campo=campo):
                payload = self.pagina()
                if campo == "duplicados":
                    payload = self.pagina([self.viaje, self.viaje])
                else:
                    payload["paginacion"][campo] = value
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(200, json=payload)
                http = await self.crearHttp(responder)
                await self.esperarError(ViajesClient(self.settings, http).listarViajes(self.conductor))
                self.assertEqual(len(requests), 1)

    async def test_listado_que_incumple_filtros_no_devuelve_datos_parciales(self) -> None:
        for filtros in ({"conductorId": 26}, {"vehiculoId": 13}, {"desde": date(2026, 10, 26)}, {"hasta": date(2026, 10, 24)}):
            with self.subTest(filtros=filtros):
                requests = []
                def responder(request):
                    requests.append(request)
                    return httpx.Response(200, json=self.pagina())
                http = await self.crearHttp(responder)
                await self.esperarError(ViajesClient(self.settings, http).listarTodosLosViajes(self.conductor, **filtros))
                self.assertEqual(len(requests), 1)

    async def test_ids_duplicados_entre_paginas_no_producen_una_lista_parcial(self) -> None:
        datos = [viaje for viaje in self.viajesDatos if viaje["conductorId"] == 27]
        requests = []
        def responder(request):
            requests.append(request)
            pagina = int(request.url.params["pagina"])
            return httpx.Response(200, json=self.pagina(datos[:50] if pagina == 1 else [datos[0]], pagina=pagina, total=51))
        http = await self.crearHttp(responder)
        await self.esperarError(ViajesClient(self.settings, http).listarTodosLosViajes(self.conductor, conductorId=27))
        self.assertEqual(len(requests), 2)

    async def test_cambio_de_totales_entre_paginas_es_503(self) -> None:
        datos = [viaje for viaje in self.viajesDatos if viaje["conductorId"] == 27]
        requests = []
        def responder(request):
            requests.append(request)
            pagina = int(request.url.params["pagina"])
            if pagina == 1:
                payload = self.pagina(datos[:50], pagina=1, total=51)
            else:
                payload = self.pagina([datos[50], datos[50] | {"viajeId": 1051}], pagina=2, total=52)
            return httpx.Response(200, json=payload)
        http = await self.crearHttp(responder)
        await self.esperarError(ViajesClient(self.settings, http).listarTodosLosViajes(self.conductor, conductorId=27))
        self.assertEqual(len(requests), 2)

    async def test_segunda_pagina_tecnicamente_invalida_no_devuelve_los_primeros_50(self) -> None:
        datos = [viaje for viaje in self.viajesDatos if viaje["conductorId"] == 27]
        requests = []
        def responder(request):
            requests.append(request)
            if request.url.params["pagina"] == "1":
                return httpx.Response(200, json=self.pagina(datos[:50], pagina=1, total=51))
            return httpx.Response(200, json={"datos": DATO_PRIVADO})
        http = await self.crearHttp(responder)
        await self.esperarError(ViajesClient(self.settings, http).listarTodosLosViajes(self.conductor, conductorId=27))
        self.assertEqual([request.url.params["pagina"] for request in requests], ["1", "2", "2"])

    async def test_inputs_invalidos_se_rechazan_antes_de_hacer_http(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(200, json=self.viaje)
        http = await self.crearHttp(responder)
        viajes, vehiculos = ViajesClient(self.settings, http, self.serviceKey), VehiculosClient(self.settings, http)
        for value in (0, -1, True, "305", 305.0):
            with self.subTest(id=value):
                await self.esperarError(viajes.obtenerViaje(value, self.conductor), 400, "SOLICITUD_INVALIDA")
                await self.esperarError(vehiculos.obtenerVehiculo(value, self.conductor), 400, "SOLICITUD_INVALIDA")
        for value in (-1, True, 1.0, "1"):
            with self.subTest(cupos=value):
                await self.esperarError(viajes.actualizarOcupacion(305, value), 400, "SOLICITUD_INVALIDA")
        for filtros in ({"conductorId": 0}, {"vehiculoId": True}, {"pagina": 0}, {"desde": "2026-10-01"}, {"desde": datetime.now(UTC)}, {"desde": date(2026, 10, 31), "hasta": date(2026, 10, 1)}):
            with self.subTest(filtros=filtros):
                await self.esperarError(viajes.listarViajes(self.conductor, **filtros), 400, "SOLICITUD_INVALIDA")
        self.assertEqual(requests, [])

    async def test_service_key_ausente_falla_500_sin_http_y_get_no_carga_esa_configuracion(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(200, json=self.viaje)
        http = await self.crearHttp(responder)
        cliente = ViajesClient(self.settings, http)
        with patch("app.clients.viajes_client.getServiceAuthSettings", return_value=SimpleNamespace(serviceApiKey=SecretStr(" "))) as provider:
            self.assertEqual((await cliente.obtenerViaje(305, self.conductor)).viajeId, 305)
            provider.assert_not_called()
            await self.esperarError(cliente.actualizarOcupacion(305, 3), 500, "ERROR_INTERNO")
            provider.assert_called_once_with()
        self.assertEqual(len(requests), 1)

    async def test_correlacion_se_genera_o_reutiliza_del_contexto_sin_enviar_valores_invalidos(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(200, json=self.viaje)
        http = await self.crearHttp(responder)
        cliente = ViajesClient(self.settings, http)
        await cliente.obtenerViaje(305, self.conductor)
        generated = requests[0].headers["X-Correlation-Id"]
        self.assertEqual(str(UUID(generated)), generated)
        application = crearAplicacion()
        @application.get("/pruebas/contexto-cliente")
        async def consultar():
            viaje = await cliente.obtenerViaje(305, self.conductor)
            return {"viajeId": viaje.viajeId}
        interno = await self.enterAsyncContext(ASYNC_CLIENT_CLASS(transport=httpx.ASGITransport(app=application, raise_app_exceptions=True), base_url="http://testserver", trust_env=False))
        response = await interno.get("/pruebas/contexto-cliente", headers={"X-Correlation-Id": self.correlationId.upper()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(requests[-1].headers["X-Correlation-Id"], self.correlationId)
        await self.esperarError(cliente.obtenerViaje(305, self.conductor, "uuid-invalido"), 500, "ERROR_INTERNO")
        self.assertEqual(len(requests), 2)

    async def test_dependencias_cierran_sesion_al_terminar_o_fallar_el_consumidor(self) -> None:
        for provider, modulo, fallo in ((getViajesClient, "viajes_client", False), (getViajesClient, "viajes_client", True), (getVehiculosClient, "vehiculos_client", False), (getVehiculosClient, "vehiculos_client", True)):
            with self.subTest(provider=provider.__name__, fallo=fallo):
                creadas = []
                def crear(*args, **kwargs):
                    session = ASYNC_CLIENT_CLASS(*args, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=self.viaje)), **kwargs)
                    creadas.append(session)
                    return session
                with patch("app.clients." + modulo + ".httpx.AsyncClient", side_effect=crear):
                    dependencia = provider(self.settings)
                    cliente = await anext(dependencia)
                    self.assertIsNotNone(cliente)
                    self.assertEqual(len(creadas), 1)
                    self.assertFalse(creadas[0].is_closed)
                    if fallo:
                        with self.assertRaises(RuntimeError):
                            await dependencia.athrow(RuntimeError("Consumidor sintético interrumpido."))
                    else:
                        await dependencia.aclose()
                    self.assertTrue(creadas[0].is_closed)

    async def test_cliente_no_cierra_la_sesion_externa_y_put_reintenta_el_mismo_total(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            return httpx.Response(503, text=DATO_PRIVADO) if len(requests) == 1 else httpx.Response(200, json=self.ocupacion())
        http = await self.crearHttp(responder)
        resultado = await ViajesClient(self.settings, http, self.serviceKey).actualizarOcupacion(305, 3, self.correlationId)
        self.assertEqual(resultado.cuposDisponibles, 1)
        self.assertFalse(http.is_closed)
        self.assertEqual(len(requests), 2)
        for request in requests:
            self.assertEqual(json.loads(request.content), {"cuposOcupados": 3})
            self.assertNotIn("Authorization", request.headers)
            self.assertEqual(request.headers["X-Service-Key"], self.serviceKey.get_secret_value())
            self.assertEqual(request.headers["X-Correlation-Id"], self.correlationId)

    async def test_logs_no_revelan_cuerpos_cabeceras_tokens_llaves_ni_causa_privada(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            if len(requests) == 1:
                raise httpx.ConnectError(DATO_PRIVADO + CABECERA_PRIVADA, request=request)
            if len(requests) == 2:
                return httpx.Response(200, json=self.viaje)
            return httpx.Response(404, json=self.errorProveedor(request, 404, "VIAJE_NO_ENCONTRADO"), headers={"X-Private": CABECERA_PRIVADA})
        http = await self.crearHttp(responder)
        cliente = ViajesClient(self.settings, http)
        with capturarLogs() as captura:
            self.assertEqual((await cliente.obtenerViaje(305, self.conductor, self.correlationId)).viajeId, 305)
            await self.esperarError(cliente.obtenerViaje(305, self.conductor, self.correlationId), 404, "VIAJE_NO_ENCONTRADO")
        self.assertGreaterEqual(len(captura.registros), 3)
        for record in captura.registros:
            self.assertEqual(getattr(record, "correlationId", None), self.correlationId)
            self.assertIsNone(record.exc_info)
            for privado in (DATO_PRIVADO, CABECERA_PRIVADA, self.secret.get_secret_value(), self.serviceKey.get_secret_value(), self.conductor.token.get_secret_value()):
                self.assertNotIn(privado, record.getMessage())

    async def test_clientes_no_usan_sql_usuarios_ni_agregan_rutas_de_negocio(self) -> None:
        requests = []
        def responder(request):
            requests.append(request)
            self.assertIn(request.url.host, ("viajes.test", "vehiculos.test"))
            return httpx.Response(200, json=self.viaje if request.url.host == "viajes.test" else self.vehiculo)
        http = await self.crearHttp(responder)
        with (
            patch("app.config.database.getEngine", side_effect=AssertionError("No usar SQL.")) as engine,
            patch("app.config.database.getSessionFactory", side_effect=AssertionError("No usar SQL.")) as sesiones,
        ):
            self.assertEqual((await ViajesClient(self.settings, http).obtenerViaje(305, self.conductor)).viajeId, 305)
            self.assertEqual((await VehiculosClient(self.settings, http).obtenerVehiculo(12, self.conductor)).vehiculoId, 12)
        engine.assert_not_called()
        sesiones.assert_not_called()
        self.assertEqual(len(requests), 2)
        paths = aplicacionProduccion.openapi()["paths"]
        self.assertEqual(set(paths), RUTAS_CONTRATO)
        self.assertEqual(set(paths["/api/v1/reservas/viaje/{viajeId}"]), {"get"})


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VerificacionClientes)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
