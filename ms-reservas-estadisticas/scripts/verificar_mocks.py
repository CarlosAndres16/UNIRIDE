"""Verifica los mocks en memoria con claves efímeras, sin SQL ni red externa."""

from contextlib import contextmanager
from datetime import date, datetime, timedelta
from tests.contrato import RUTAS_CONTRATO

import logging
import secrets
import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import jwt
from pydantic import SecretStr

from app.main import app as aplicacionProduccion
from app.schemas.error_schema import ErrorResponse
from app.security.jwt_service import JwtService, getJwtService
from mocks.common import getServiceApiKey
from mocks.schemas import VehiculoMock, ViajeMock
from mocks.vehiculos_mock import crearVehiculosMock
from mocks.viajes_mock import crearViajesMock

HEADER_CORRELACION = "X-Correlation-Id"
CAMPOS_VIAJE = {
    "viajeId", "conductorId", "vehiculoId", "origen", "destino", "fechaSalida",
    "horaSalida", "capacidad", "cuposDisponibles", "estado", "version",
    "fechaCreacion", "fechaActualizacion",
}
CAMPOS_VEHICULO = {
    "vehiculoId", "conductorId", "placa", "marca", "modelo", "color", "tipo",
    "capacidad", "estado",
}
CAMPOS_OCUPACION = {
    "viajeId", "capacidad", "cuposDisponibles", "estado", "version", "fechaActualizacion",
}
DATO_PRIVADO = "DATO_PRIVADO_DEL_MOCK_NO_PUBLICAR_1FBE8A"


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


class VerificacionMocks(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = SecretStr(secrets.token_urlsafe(64))
        self.serviceKey = SecretStr(secrets.token_urlsafe(64))
        self.jwtService = JwtService(self.secret)
        self.viajesApp = crearViajesMock()
        self.vehiculosApp = crearVehiculosMock()
        self.viajes = self.prepararCliente(self.viajesApp)
        self.vehiculos = self.prepararCliente(self.vehiculosApp)

    def prepararCliente(self, application):
        application.dependency_overrides[getJwtService] = lambda: self.jwtService
        application.dependency_overrides[getServiceApiKey] = lambda: self.serviceKey
        return self.enterContext(TestClient(application, raise_server_exceptions=True))

    def emitirToken(self, conductorId: int = 25, *, vencido: bool = False, otraFirma: bool = False) -> str:
        ahora = int(time.time())
        secret = secrets.token_urlsafe(64) if otraFirma else self.secret.get_secret_value()
        return jwt.encode(
            {"sub": str(conductorId), "iat": ahora - 3600, "exp": ahora - 1 if vencido else ahora + 3600},
            secret,
            algorithm="HS256",
        )

    def headersConductor(self, conductorId: int = 25) -> dict[str, str]:
        return {"Authorization": "Bearer " + self.emitirToken(conductorId)}

    def headersServicio(self) -> dict[str, str]:
        return {"X-Service-Key": self.serviceKey.get_secret_value()}

    def comprobarCorrelacion(self, response) -> str:
        correlationId = response.headers.get(HEADER_CORRELACION)
        self.assertIsNotNone(correlationId)
        self.assertEqual(str(UUID(correlationId)), correlationId)
        return correlationId

    def comprobarUtc(self, value: str) -> datetime:
        self.assertTrue(value.endswith("Z"))
        resultado = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self.assertEqual(resultado.utcoffset(), timedelta(0))
        return resultado

    def comprobarError(self, response, status: int, codigo: str | None = None) -> dict:
        self.assertEqual(response.status_code, status)
        correlationId = self.comprobarCorrelacion(response)
        body = response.json()
        campos = {"timestamp", "status", "error", "message", "path", "correlationId"}
        if status == 400:
            campos.add("detalles")
            self.assertIsInstance(body.get("detalles"), list)
            for detalle in body["detalles"]:
                self.assertEqual(set(detalle), {"campo", "problema"})
        self.assertEqual(set(body), campos)
        self.assertEqual(body["status"], status)
        self.assertEqual(body["path"], response.request.url.path)
        self.assertEqual(body["correlationId"], correlationId)
        if codigo is not None:
            self.assertEqual(body["error"], codigo)
        self.comprobarUtc(body["timestamp"])
        ErrorResponse.model_validate(body)
        for privado in (self.secret.get_secret_value(), self.serviceKey.get_secret_value(), DATO_PRIVADO):
            self.assertNotIn(privado, response.text)
        self.assertNotIn('"input"', response.text)
        return body

    def comprobarViaje(self, body: dict) -> None:
        self.assertEqual(set(body), CAMPOS_VIAJE)
        for campo in ("viajeId", "conductorId", "vehiculoId", "capacidad", "cuposDisponibles", "version"):
            self.assertIs(type(body[campo]), int)
        for campo in ("origen", "destino"):
            self.assertEqual(set(body[campo]), {"descripcion", "latitud", "longitud"})
            self.assertIsInstance(body[campo]["descripcion"], str)
            self.assertTrue(body[campo]["descripcion"])
        self.assertEqual(date.fromisoformat(body["fechaSalida"]).isoformat(), body["fechaSalida"])
        self.assertEqual(len(body["horaSalida"]), 5)
        datetime.strptime(body["horaSalida"], "%H:%M")
        self.comprobarUtc(body["fechaCreacion"])
        self.comprobarUtc(body["fechaActualizacion"])
        self.assertIn(body["estado"], ("ACTIVO", "FINALIZADO", "CANCELADO"))
        ViajeMock.model_validate(body)

    def listar(self, **params) -> dict:
        response = self.viajes.get("/api/v1/viajes", params=params, headers=self.headersConductor())
        self.assertEqual(response.status_code, 200)
        self.comprobarCorrelacion(response)
        body = response.json()
        self.assertEqual(set(body), {"datos", "paginacion"})
        self.assertEqual(set(body["paginacion"]), {"pagina", "tamano", "totalElementos", "totalPaginas"})
        self.assertEqual([viaje["viajeId"] for viaje in body["datos"]], sorted(viaje["viajeId"] for viaje in body["datos"]))
        for viaje in body["datos"]:
            self.comprobarViaje(viaje)
        return body

    def consultar305(self, client=None) -> dict:
        response = (client or self.viajes).get("/api/v1/viajes/305", headers=self.headersConductor())
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_rutas_mock_exactas_y_produccion_solo_reservas_por_viaje(self) -> None:
        pathsViajes = self.viajes.get("/openapi.json").json()["paths"]
        self.assertEqual(set(pathsViajes), {
            "/api/v1/viajes", "/api/v1/viajes/{viajeId}", "/api/v1/viajes/{viajeId}/ocupacion",
        })
        self.assertEqual(set(pathsViajes["/api/v1/viajes"]), {"get"})
        self.assertEqual(set(pathsViajes["/api/v1/viajes/{viajeId}"]), {"get"})
        self.assertEqual(set(pathsViajes["/api/v1/viajes/{viajeId}/ocupacion"]), {"put"})
        pathsVehiculos = self.vehiculos.get("/openapi.json").json()["paths"]
        self.assertEqual(set(pathsVehiculos), {"/api/v1/vehiculos/{vehiculoId}"})
        self.assertEqual(set(pathsVehiculos["/api/v1/vehiculos/{vehiculoId}"]), {"get"})
        with TestClient(aplicacionProduccion, raise_server_exceptions=True) as client:
            paths = client.get("/openapi.json").json()["paths"]
            self.assertEqual(set(paths), RUTAS_CONTRATO)
            self.assertEqual(set(paths["/api/v1/reservas/viaje/{viajeId}"]), {"get"})

    def test_viaje_principal_respeta_json_camelcase_y_tiempos(self) -> None:
        response = self.viajes.get("/api/v1/viajes/305", headers=self.headersConductor())
        self.assertEqual(response.status_code, 200)
        self.comprobarCorrelacion(response)
        body = response.json()
        self.comprobarViaje(body)
        self.assertEqual(
            {campo: body[campo] for campo in ("viajeId", "conductorId", "vehiculoId", "capacidad", "cuposDisponibles", "estado")},
            {"viajeId": 305, "conductorId": 25, "vehiculoId": 12, "capacidad": 4, "cuposDisponibles": 2, "estado": "ACTIVO"},
        )
        self.assertEqual(body["horaSalida"], "07:00")

    def test_vehiculos_propios_activo_e_inactivo_respetan_json(self) -> None:
        for vehiculoId, estado in ((12, "ACTIVO"), (15, "INACTIVO")):
            with self.subTest(vehiculoId=vehiculoId):
                response = self.vehiculos.get(f"/api/v1/vehiculos/{vehiculoId}", headers=self.headersConductor())
                self.assertEqual(response.status_code, 200)
                self.comprobarCorrelacion(response)
                body = response.json()
                self.assertEqual(set(body), CAMPOS_VEHICULO)
                self.assertEqual(body["vehiculoId"], vehiculoId)
                self.assertEqual(body["conductorId"], 25)
                self.assertEqual(body["estado"], estado)
                VehiculoMock.model_validate(body)

    def test_ambos_mocks_exigen_jwt_valido_no_vencido_y_firma_correcta(self) -> None:
        casos = (
            {},
            {"Authorization": "Bearer token-invalido"},
            {"Authorization": "Bearer " + self.emitirToken(otraFirma=True)},
            {"Authorization": "Bearer " + self.emitirToken(vencido=True)},
        )
        for client, path in ((self.viajes, "/api/v1/viajes/305"), (self.vehiculos, "/api/v1/vehiculos/12")):
            for indice, headers in enumerate(casos):
                with self.subTest(path=path, caso=indice):
                    response = client.get(path, headers=headers)
                    self.comprobarError(response, 401, "NO_AUTENTICADO")
                    self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")

    def test_uuid_invalido_es_400_con_uuid_nuevo_en_ambos_mocks(self) -> None:
        for client, path in ((self.viajes, "/api/v1/viajes/305"), (self.vehiculos, "/api/v1/vehiculos/12")):
            with self.subTest(path=path):
                response = client.get(path, headers=self.headersConductor() | {HEADER_CORRELACION: "uuid-invalido"})
                body = self.comprobarError(response, 400, "FORMATO_INVALIDO")
                self.assertEqual(body["detalles"][0]["campo"], HEADER_CORRELACION)

    def test_recursos_ajenos_403_e_inexistentes_404_sin_datos_del_recurso(self) -> None:
        casos = (
            (self.viajes, "/api/v1/viajes/309", 403, "NO_AUTORIZADO"),
            (self.vehiculos, "/api/v1/vehiculos/14", 403, "NO_AUTORIZADO"),
            (self.viajes, "/api/v1/viajes/999999", 404, "VIAJE_NO_ENCONTRADO"),
            (self.vehiculos, "/api/v1/vehiculos/999999", 404, "VEHICULO_NO_ENCONTRADO"),
        )
        for client, path, status, codigo in casos:
            with self.subTest(path=path):
                response = client.get(path, headers=self.headersConductor())
                self.comprobarError(response, status, codigo)
                self.assertNotIn('"origen"', response.text)
                self.assertNotIn('"placa"', response.text)

    def test_listado_default_activo_abierto_sin_filtro_implicito_por_jwt(self) -> None:
        body = self.listar()
        self.assertEqual(body["paginacion"], {"pagina": 1, "tamano": 20, "totalElementos": 54, "totalPaginas": 3})
        self.assertTrue(all(viaje["estado"] == "ACTIVO" for viaje in body["datos"]))
        self.assertIn(309, [viaje["viajeId"] for viaje in body["datos"]])
        self.assertTrue(any(viaje["conductorId"] != 25 for viaje in body["datos"]))

    def test_listado_filtra_conductor_vehiculo_y_su_combinacion(self) -> None:
        casos = (
            ({"conductorId": 25}, [305, 306, 307, 308]),
            ({"conductorId": 26}, [309]),
            ({"vehiculoId": 12}, [305, 306, 307]),
            ({"vehiculoId": 13}, [308]),
            ({"conductorId": 25, "vehiculoId": 12}, [305, 306, 307]),
        )
        for filtros, esperados in casos:
            with self.subTest(filtros=filtros):
                body = self.listar(estado="TODOS", **filtros)
                self.assertEqual([viaje["viajeId"] for viaje in body["datos"]], esperados)

    def test_listado_filtra_los_tres_estados_y_todos(self) -> None:
        for estado, esperados in (
            ("ACTIVO", [305, 308]), ("FINALIZADO", [306]),
            ("CANCELADO", [307]), ("TODOS", [305, 306, 307, 308]),
        ):
            with self.subTest(estado=estado):
                body = self.listar(conductorId=25, estado=estado)
                self.assertEqual([viaje["viajeId"] for viaje in body["datos"]], esperados)

    def test_fechas_del_listado_son_inclusivas_y_admiten_un_solo_limite(self) -> None:
        casos = (
            ({"desde": "2026-10-01", "hasta": "2026-10-31"}, [305, 306, 307, 308]),
            ({"desde": "2026-10-01", "hasta": "2026-10-01"}, [306]),
            ({"desde": "2026-10-31", "hasta": "2026-10-31"}, [307]),
            ({"desde": "2026-10-25", "hasta": "2026-10-26"}, [305, 308]),
            ({"desde": "2026-10-26"}, [307, 308]),
            ({"hasta": "2026-10-01"}, [306]),
        )
        for filtros, esperados in casos:
            with self.subTest(filtros=filtros):
                body = self.listar(conductorId=25, estado="TODOS", **filtros)
                self.assertEqual([viaje["viajeId"] for viaje in body["datos"]], esperados)

    def test_fechas_invalidas_y_periodo_invertido_devuelven_400(self) -> None:
        casos = (
            ({"desde": "2026-02-30"}, "FECHA_HORA_INVALIDA"),
            ({"hasta": "2026-1-01"}, "FECHA_HORA_INVALIDA"),
            ({"desde": "2026-10-25T00:00:00"}, "FECHA_HORA_INVALIDA"),
            ({"desde": "2026-10-31", "hasta": "2026-10-01"}, "SOLICITUD_INVALIDA"),
        )
        for filtros, codigo in casos:
            with self.subTest(filtros=filtros):
                response = self.viajes.get("/api/v1/viajes", params=filtros, headers=self.headersConductor())
                self.comprobarError(response, 400, codigo)

    def test_estado_ids_y_paginacion_invalidos_devuelven_400(self) -> None:
        casos = (
            {"estado": "PENDIENTE"}, {"conductorId": -1}, {"vehiculoId": 0},
            {"pagina": 0}, {"tamano": 0}, {"tamano": 51},
        )
        for params in casos:
            with self.subTest(params=params):
                response = self.viajes.get("/api/v1/viajes", params=params, headers=self.headersConductor())
                self.comprobarError(response, 400)
        for client, path in ((self.viajes, "/api/v1/viajes/-1"), (self.vehiculos, "/api/v1/vehiculos/0")):
            with self.subTest(path=path):
                self.comprobarError(client.get(path, headers=self.headersConductor()), 400)

    def test_listado_vacio_es_200_con_totales_cero(self) -> None:
        body = self.listar(conductorId=999999, estado="TODOS")
        self.assertEqual(body["datos"], [])
        self.assertEqual(body["paginacion"], {"pagina": 1, "tamano": 20, "totalElementos": 0, "totalPaginas": 0})

    def test_pagina_posterior_al_final_es_lista_vacia(self) -> None:
        body = self.listar(conductorId=27, estado="TODOS", pagina=3, tamano=50)
        self.assertEqual(body["datos"], [])
        self.assertEqual(body["paginacion"], {"pagina": 3, "tamano": 50, "totalElementos": 51, "totalPaginas": 2})

    def test_recorre_51_viajes_en_dos_paginas_sin_duplicados(self) -> None:
        ids = []
        horas = []
        for pagina, esperados in ((1, 50), (2, 1)):
            body = self.listar(conductorId=27, estado="TODOS", pagina=pagina, tamano=50)
            self.assertEqual(body["paginacion"], {"pagina": pagina, "tamano": 50, "totalElementos": 51, "totalPaginas": 2})
            self.assertEqual(len(body["datos"]), esperados)
            self.assertTrue(all(viaje["conductorId"] == 27 and viaje["vehiculoId"] == 16 and viaje["fechaSalida"] == "2026-10-25" for viaje in body["datos"]))
            ids.extend(viaje["viajeId"] for viaje in body["datos"])
            horas.extend(viaje["horaSalida"] for viaje in body["datos"])
        self.assertEqual(ids, list(range(1000, 1051)))
        self.assertEqual(len(set(ids)), 51)
        self.assertEqual(len(set(horas)), 51)

    def test_put_solo_necesita_service_key_y_no_carga_jwt(self) -> None:
        self.viajesApp.dependency_overrides.pop(getJwtService)
        with patch("app.security.jwt_service.getJwtSettings", side_effect=AssertionError("No cargar JWT para PUT interno.")) as configuracion:
            response = self.viajes.put("/api/v1/viajes/305/ocupacion", json={"cuposOcupados": 1}, headers=self.headersServicio())
        configuracion.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.comprobarCorrelacion(response)
        self.assertEqual(set(response.json()), CAMPOS_OCUPACION)
        self.assertEqual(response.json()["cuposDisponibles"], 3)

    def test_put_sin_llave_incorrecta_vacia_o_duplicada_es_401(self) -> None:
        llave = self.serviceKey.get_secret_value()
        casos = (
            {}, self.headersConductor(), {"X-Service-Key": DATO_PRIVADO},
            {"X-Service-Key": ""}, [("X-Service-Key", llave), ("X-Service-Key", llave)],
        )
        for indice, headers in enumerate(casos):
            with self.subTest(caso=indice):
                response = self.viajes.put("/api/v1/viajes/305/ocupacion", json={"cuposOcupados": 1}, headers=headers)
                self.comprobarError(response, 401, "NO_AUTENTICADO")

    def test_put_body_estricto_rechaza_ausentes_negativos_float_bool_string_y_extras(self) -> None:
        antes = self.consultar305()
        casos = (
            {}, {"cuposOcupados": -1}, {"cuposOcupados": 1.5},
            {"cuposOcupados": True}, {"cuposOcupados": "1"},
            {"cuposOcupados": 1, "extra": DATO_PRIVADO},
        )
        for body in casos:
            with self.subTest(body=body):
                response = self.viajes.put("/api/v1/viajes/305/ocupacion", json=body, headers=self.headersServicio())
                self.comprobarError(response, 400)
        self.assertEqual(self.consultar305(), antes)

    def test_put_json_malformado_devuelve_400_sin_revelar_cuerpo(self) -> None:
        response = self.viajes.put(
            "/api/v1/viajes/305/ocupacion", content='{"cuposOcupados": "' + DATO_PRIVADO + '"',
            headers=self.headersServicio() | {"Content-Type": "application/json"},
        )
        self.comprobarError(response, 400, "FORMATO_INVALIDO")

    def test_put_no_permite_superar_capacidad_y_conserva_estado(self) -> None:
        antes = self.consultar305()
        response = self.viajes.put("/api/v1/viajes/305/ocupacion", json={"cuposOcupados": 5}, headers=self.headersServicio())
        self.comprobarError(response, 400, "CAPACIDAD_INVALIDA")
        self.assertEqual(self.consultar305(), antes)

    def test_put_viaje_inexistente_es_404(self) -> None:
        response = self.viajes.put("/api/v1/viajes/999999/ocupacion", json={"cuposOcupados": 1}, headers=self.headersServicio())
        self.comprobarError(response, 404, "VIAJE_NO_ENCONTRADO")

    def test_put_finalizado_o_cancelado_es_409_sin_mutacion(self) -> None:
        for viajeId in (306, 307):
            with self.subTest(viajeId=viajeId):
                path = f"/api/v1/viajes/{viajeId}"
                antes = self.viajes.get(path, headers=self.headersConductor()).json()
                response = self.viajes.put(path + "/ocupacion", json={"cuposOcupados": 1}, headers=self.headersServicio())
                self.comprobarError(response, 409, "OPERACION_NO_PERMITIDA_POR_ESTADO")
                self.assertEqual(self.viajes.get(path, headers=self.headersConductor()).json(), antes)

    def test_put_usa_total_y_es_idempotente_incluidos_cero_y_capacidad(self) -> None:
        anterior = self.consultar305()
        for ocupados in (1, 1, 3, 0, 0, 4, 4):
            with self.subTest(cuposOcupados=ocupados):
                response = self.viajes.put("/api/v1/viajes/305/ocupacion", json={"cuposOcupados": ocupados}, headers=self.headersServicio())
                self.assertEqual(response.status_code, 200)
                self.comprobarCorrelacion(response)
                body = response.json()
                self.assertEqual(set(body), CAMPOS_OCUPACION)
                self.assertEqual(body["cuposDisponibles"], 4 - ocupados)
                cambio = anterior["cuposDisponibles"] != 4 - ocupados
                self.assertEqual(body["version"], anterior["version"] + int(cambio))
                fecha = self.comprobarUtc(body["fechaActualizacion"])
                if not cambio:
                    self.assertEqual(body["fechaActualizacion"], anterior["fechaActualizacion"])
                else:
                    self.assertGreaterEqual(fecha, self.comprobarUtc(anterior["fechaActualizacion"]))
                actual = self.consultar305()
                for campo in CAMPOS_OCUPACION:
                    self.assertEqual(actual[campo], body[campo])
                anterior = actual

    def test_instancias_viajes_copian_datos_y_no_comparten_ocupacion(self) -> None:
        original = ViajeMock.model_validate(self.consultar305())
        primeraApp = crearViajesMock(viajes=[original])
        segundaApp = crearViajesMock(viajes=[original])
        primera = self.prepararCliente(primeraApp)
        segunda = self.prepararCliente(segundaApp)
        self.assertIsNot(primeraApp.state.viajes[305], original)
        self.assertIsNot(segundaApp.state.viajes[305], original)
        response = primera.put("/api/v1/viajes/305/ocupacion", json={"cuposOcupados": 0}, headers=self.headersServicio())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.consultar305(primera)["cuposDisponibles"], 4)
        self.assertEqual(self.consultar305(segunda)["cuposDisponibles"], 2)
        self.assertEqual(original.cuposDisponibles, 2)
        self.assertEqual(self.consultar305()["cuposDisponibles"], 2)

    def test_instancias_vehiculos_copian_datos_y_no_comparten_estado(self) -> None:
        original = VehiculoMock.model_validate(self.vehiculos.get("/api/v1/vehiculos/12", headers=self.headersConductor()).json())
        primeraApp = crearVehiculosMock(vehiculos=[original])
        segundaApp = crearVehiculosMock(vehiculos=[original])
        primera = self.prepararCliente(primeraApp)
        segunda = self.prepararCliente(segundaApp)
        self.assertIsNot(primeraApp.state.vehiculos[12], original)
        self.assertIsNot(segundaApp.state.vehiculos[12], original)
        primeraApp.state.vehiculos[12] = primeraApp.state.vehiculos[12].model_copy(update={"color": "Verde"})
        self.assertEqual(primera.get("/api/v1/vehiculos/12", headers=self.headersConductor()).json()["color"], "Verde")
        self.assertEqual(segunda.get("/api/v1/vehiculos/12", headers=self.headersConductor()).json()["color"], original.color)
        self.assertEqual(original.color, "Gris")

    def test_logs_omiten_token_y_llaves_y_conservan_correlacion(self) -> None:
        token = self.emitirToken()
        ids = [str(uuid4()), str(uuid4())]
        with capturarLogs() as captura:
            response = self.viajes.get(
                "/api/v1/viajes/305", headers={"Authorization": "Bearer " + token, HEADER_CORRELACION: ids[0]},
            )
            self.assertEqual(response.status_code, 200)
            response = self.viajes.put(
                "/api/v1/viajes/305/ocupacion", json={"cuposOcupados": 1},
                headers={"X-Service-Key": DATO_PRIVADO, HEADER_CORRELACION: ids[1]},
            )
            self.comprobarError(response, 401, "NO_AUTENTICADO")
        self.assertGreaterEqual(len(captura.registros), 2)
        registrados = set()
        for record in captura.registros:
            correlationId = getattr(record, "correlationId", None)
            self.assertIn(correlationId, ids)
            registrados.add(correlationId)
            self.assertIsNone(record.exc_info)
            for privado in (token, self.secret.get_secret_value(), self.serviceKey.get_secret_value(), DATO_PRIVADO):
                self.assertNotIn(privado, record.getMessage())
        self.assertEqual(registrados, set(ids))

    def test_mocks_no_consultan_sql_ni_servicios_externos(self) -> None:
        with (
            patch("app.config.database.getEngine", side_effect=AssertionError("No usar SQL.")) as engine,
            patch("app.config.database.getSessionFactory", side_effect=AssertionError("No usar SQL.")) as sesiones,
            patch("httpx.AsyncClient.request", side_effect=AssertionError("No usar servicios.")) as http,
        ):
            self.assertEqual(self.viajes.get("/api/v1/viajes/305", headers=self.headersConductor()).status_code, 200)
            self.assertEqual(self.vehiculos.get("/api/v1/vehiculos/12", headers=self.headersConductor()).status_code, 200)
            self.assertEqual(self.viajes.put("/api/v1/viajes/305/ocupacion", json={"cuposOcupados": 1}, headers=self.headersServicio()).status_code, 200)
        engine.assert_not_called()
        sesiones.assert_not_called()
        http.assert_not_called()


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VerificacionMocks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
