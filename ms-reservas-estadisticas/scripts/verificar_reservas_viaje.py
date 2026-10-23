"""Verifica reservas por viaje con HTTP en memoria y SQL compilado, sin BD."""

from tests.contrato import RUTAS_CONTRATO

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import logging
import secrets
import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
import jwt
from pydantic import SecretStr
from sqlalchemy.dialects import mssql
from sqlalchemy.exc import SQLAlchemyError, StatementError

from app.clients.viajes_client import ViajesClient
from app.config.settings import HttpClientSettings
from app.exceptions.exceptions import ServicioDependienteNoDisponibleError
from app.main import app as aplicacionProduccion, crearAplicacion
from app.middleware.correlation_id import getCorrelationId
from app.models.reserva import EstadoReserva, Reserva
from app.repositories.reserva_repository import ReservaRepository, ResumenReservas
from app.schemas.error_schema import ErrorResponse
from app.security.jwt_service import JwtService, getJwtService
from app.services.reserva_service import ReservaService, getReservaService
from mocks.data import crearViajesEjemplo
from mocks.viajes_mock import crearViajesMock

RUTA = "/api/v1/reservas/viaje/{viajeId}"
CAMPOS_RESERVA = {
    "reservaId", "viajeId", "pasajeroNombre", "cuposReservados", "estado", "fechaReserva",
}
DATO_PRIVADO = "DATO_PRIVADO_RESERVAS_NO_PUBLICAR_C52A9B"


def crearReservasEjemplo() -> list[Reserva]:
    """Objetos ORM transitorios: no se agregan a ninguna sesion real."""
    return [
        Reserva(
            id=1, viajeId=305, pasajeroNombre="Laura Gómez", cuposReservados=1,
            estado=EstadoReserva.CONFIRMADA,
            fechaReserva=datetime(2026, 10, 1, 14, 20, tzinfo=UTC),
        ),
        Reserva(
            id=2, viajeId=305, pasajeroNombre="David Ruiz", cuposReservados=1,
            estado=EstadoReserva.CONFIRMADA,
            fechaReserva=datetime(2026, 10, 1, 14, 21, tzinfo=UTC),
        ),
        Reserva(
            id=3, viajeId=305, pasajeroNombre="Carlos Pérez", cuposReservados=1,
            estado=EstadoReserva.CANCELADA,
            fechaReserva=datetime(2026, 10, 1, 14, 22, tzinfo=UTC),
        ),
    ]


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


class RepositorioSimulado:
    def __init__(self, eventos: list[str]) -> None:
        self.datos = crearReservasEjemplo()
        self.llamadas: list[tuple[int, EstadoReserva | None]] = []
        self.eventos = eventos
        self.fallo: Exception | None = None

    def listarPorViaje(self, viajeId: int, estado: EstadoReserva | None = None):
        self.eventos.append("reservas")
        self.llamadas.append((viajeId, estado))
        if self.fallo is not None:
            raise self.fallo
        return sorted(
            [reserva for reserva in self.datos if reserva.viajeId == viajeId
             and (estado is None or reserva.estado == estado)],
            key=lambda reserva: reserva.id,
        )


    def resumirPorViajes(self, viajeIds):
        if self.fallo is not None:
            raise self.fallo
        resultado = {}
        for viajeId in viajeIds:
            datos = [r for r in self.datos if r.viajeId == viajeId]
            resultado[viajeId] = ResumenReservas(
                totalReservas=len(datos),
                reservasConfirmadas=sum(r.estado == EstadoReserva.CONFIRMADA for r in datos),
                reservasCanceladas=sum(r.estado == EstadoReserva.CANCELADA for r in datos),
                reservasPendientes=sum(r.estado == EstadoReserva.PENDIENTE for r in datos),
                pasajerosConfirmados=sum(r.cuposReservados for r in datos if r.estado == EstadoReserva.CONFIRMADA),
            )
        return resultado


class ViajesSimulado:
    def __init__(self, eventos: list[str]) -> None:
        self.eventos = eventos
        self.llamadas: list[tuple[int, object, str | None]] = []
        self.datos = {viaje.viajeId: viaje for viaje in crearViajesEjemplo()}
        self.fallo: Exception | None = None

    async def obtenerViaje(self, viajeId: int, conductor, correlationId=None):
        self.eventos.append("viajes")
        self.llamadas.append((viajeId, conductor, correlationId))
        if self.fallo is not None:
            raise self.fallo
        return self.datos[viajeId]


class TransporteViajes(httpx.AsyncBaseTransport):
    """El unico destino permitido es el mock ASGI de Viajes."""

    def __init__(self, application) -> None:
        self.requests: list[httpx.Request] = []
        self.transport = httpx.ASGITransport(app=application, raise_app_exceptions=True)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "viajes.test" or request.method != "GET":
            raise AssertionError("La consulta no debe llamar otros servicios ni modificar ocupacion.")
        self.requests.append(request)
        return await self.transport.handle_async_request(request)

    async def aclose(self) -> None:
        await self.transport.aclose()


class ResultadoSimulado:
    def __init__(self, datos) -> None:
        self.datos = datos

    def all(self):
        return list(self.datos)


class SesionSimulada:
    """Acepta una lectura SQLAlchemy, pero no abre motor ni conexion."""

    def __init__(self, datos=(), fallo: Exception | None = None) -> None:
        self.datos = list(datos)
        self.fallo = fallo
        self.consultas = []
        self.mutaciones: list[str] = []

    def scalars(self, consulta):
        self.consultas.append(consulta)
        if self.fallo is not None:
            raise self.fallo
        return ResultadoSimulado(self.datos)

    def __getattr__(self, nombre):
        if nombre in {"add", "add_all", "delete", "commit", "flush", "merge", "execute"}:
            self.mutaciones.append(nombre)
            raise AssertionError("El repositorio debe ejecutar solamente una lectura con scalars.")
        raise AttributeError(nombre)


class VerificacionReservasViaje(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = SecretStr(secrets.token_urlsafe(64))
        self.jwtService = JwtService(self.secret)
        self.eventos: list[str] = []
        self.repository = RepositorioSimulado(self.eventos)
        self.viajes = ViajesSimulado(self.eventos)
        self.service = ReservaService(self.repository, self.viajes)
        self.application = crearAplicacion()
        self.application.dependency_overrides[getJwtService] = lambda: self.jwtService
        self.application.dependency_overrides[getReservaService] = lambda: self.service
        self.enterContext(patch(
            "app.config.database.getSessionFactory",
            side_effect=AssertionError("Las pruebas no permiten abrir sesiones SQL reales."),
        ))
        self.client = self.enterContext(TestClient(self.application, raise_server_exceptions=True))

    def emitirToken(self, conductorId: int = 25, *, vencido=False, otraFirma=False) -> str:
        ahora = int(time.time())
        secret = secrets.token_urlsafe(64) if otraFirma else self.secret.get_secret_value()
        return jwt.encode(
            {"sub": str(conductorId), "iat": ahora - 3600,
             "exp": ahora - 1 if vencido else ahora + 3600},
            secret, algorithm="HS256",
        )

    def headers(self, conductorId: int = 25, **extra) -> dict[str, str]:
        return {"Authorization": "Bearer " + self.emitirToken(conductorId), **extra}

    def consultar(self, viajeId=305, *, headers=None, **params):
        return self.client.get(
            f"/api/v1/reservas/viaje/{viajeId}",
            headers=self.headers() if headers is None else headers,
            params=params,
        )

    def comprobarCorrelacion(self, response) -> str:
        correlationId = response.headers.get("X-Correlation-Id")
        self.assertIsNotNone(correlationId)
        self.assertEqual(str(UUID(correlationId)), correlationId)
        return correlationId

    def comprobarUtc(self, timestamp: str) -> None:
        self.assertTrue(timestamp.endswith("Z"))
        self.assertEqual(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).utcoffset(), timedelta(0))

    def comprobarError(self, response, status: int, codigo: str | None = None) -> dict:
        self.assertEqual(response.status_code, status)
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
        self.assertEqual(body["correlationId"], self.comprobarCorrelacion(response))
        self.comprobarUtc(body["timestamp"])
        if codigo is not None:
            self.assertEqual(body["error"], codigo)
        ErrorResponse.model_validate(body)
        self.assertNotIn(DATO_PRIVADO, response.text)
        self.assertNotIn(self.secret.get_secret_value(), response.text)
        self.assertNotIn('"input"', response.text)
        return body

    def comprobarListado(self, response, viajeId: int, ids: list[int]) -> dict:
        self.assertEqual(response.status_code, 200)
        self.comprobarCorrelacion(response)
        body = response.json()
        self.assertEqual(set(body), {"viajeId", "total", "datos"})
        self.assertEqual(body["viajeId"], viajeId)
        self.assertIs(type(body["viajeId"]), int)
        self.assertIs(type(body["total"]), int)
        self.assertEqual(body["total"], len(ids))
        self.assertEqual([reserva["reservaId"] for reserva in body["datos"]], ids)
        for reserva in body["datos"]:
            self.assertEqual(set(reserva), CAMPOS_RESERVA)
            self.assertEqual(reserva["viajeId"], viajeId)
            for campo in ("reservaId", "viajeId", "cuposReservados"):
                self.assertIs(type(reserva[campo]), int)
                self.assertGreater(reserva[campo], 0)
            self.assertIn(reserva["estado"], {estado.value for estado in EstadoReserva})
            self.comprobarUtc(reserva["fechaReserva"])
        return body

    def usarClienteViajesReal(self) -> TransporteViajes:
        application = crearViajesMock()
        application.dependency_overrides[getJwtService] = lambda: self.jwtService
        transporte = TransporteViajes(application)
        httpClient = httpx.AsyncClient(transport=transporte, trust_env=False)
        self.addCleanup(lambda: asyncio.run(httpClient.aclose()))
        settings = HttpClientSettings(
            _env_file=None, VIAJES_SERVICE_URL="http://viajes.test",
            VEHICULOS_SERVICE_URL="http://vehiculos.test",
            HTTP_TIMEOUT_MS=3000, HTTP_MAX_RETRIES=1,
        )
        self.service = ReservaService(self.repository, ViajesClient(settings, httpClient))
        return transporte

    def test_01_contrato_publica_solo_get_protegido(self):
        paths = aplicacionProduccion.openapi()["paths"]
        self.assertEqual(set(paths), RUTAS_CONTRATO)
        self.assertEqual(set(paths[RUTA]), {"get"})
        self.assertTrue(paths[RUTA]["get"].get("security"))
        self.assertIn("200", paths[RUTA]["get"]["responses"])

    def test_02_propietario_recibe_tres_reservas_con_dto_y_utc(self):
        body = self.comprobarListado(self.consultar(), 305, [1, 2, 3])
        self.assertEqual([reserva["pasajeroNombre"] for reserva in body["datos"]],
                         ["Laura Gómez", "David Ruiz", "Carlos Pérez"])
        self.assertEqual([reserva["fechaReserva"] for reserva in body["datos"]],
                         ["2026-10-01T14:20:00Z", "2026-10-01T14:21:00Z", "2026-10-01T14:22:00Z"])
        self.assertEqual([reserva["estado"] for reserva in body["datos"]],
                         ["CONFIRMADA", "CONFIRMADA", "CANCELADA"])
        self.assertEqual(self.eventos, ["viajes", "reservas"])
        self.assertEqual(self.repository.llamadas, [(305, None)])

    def test_03_filtros_los_tres_estados_incluyen_pendiente_vacio(self):
        for estado, ids in ((EstadoReserva.PENDIENTE, []),
                            (EstadoReserva.CONFIRMADA, [1, 2]),
                            (EstadoReserva.CANCELADA, [3])):
            with self.subTest(estado=estado):
                body = self.comprobarListado(self.consultar(estado=estado.value), 305, ids)
                self.assertTrue(all(reserva["estado"] == estado.value for reserva in body["datos"]))
                self.assertEqual(self.repository.llamadas[-1], (305, estado))
                self.assertIsInstance(self.repository.llamadas[-1][1], EstadoReserva)

    def test_04_viaje_propio_sin_reservas_devuelve_200_vacio(self):
        self.comprobarListado(self.consultar(308), 308, [])
        self.assertEqual(self.eventos, ["viajes", "reservas"])
        self.assertEqual(self.repository.llamadas, [(308, None)])

    def test_05_jwt_ausente_invalido_vencido_o_firma_ajena_401_sin_repo(self):
        casos = [None, "Bearer invalido", "Basic invalido", "Bearer ",
                 "Bearer " + self.emitirToken(vencido=True),
                 "Bearer " + self.emitirToken(otraFirma=True)]
        for authorization in casos:
            with self.subTest(caso=casos.index(authorization)):
                headers = {} if authorization is None else {"Authorization": authorization}
                response = self.consultar(headers=headers)
                self.comprobarError(response, 401, "NO_AUTENTICADO")
                self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")
        self.assertEqual(self.repository.llamadas, [])
        self.assertEqual(self.viajes.llamadas, [])

    def test_06_viaje_ajeno_mock_devuelve_403_antes_del_repositorio(self):
        transporte = self.usarClienteViajesReal()
        self.comprobarError(self.consultar(309), 403, "NO_AUTORIZADO")
        self.assertEqual(self.repository.llamadas, [])
        self.assertEqual(len(transporte.requests), 1)
        self.assertEqual(transporte.requests[0].url.path, "/api/v1/viajes/309")

    def test_07_viaje_inexistente_mock_devuelve_404_antes_del_repositorio(self):
        transporte = self.usarClienteViajesReal()
        self.comprobarError(self.consultar(999999), 404, "VIAJE_NO_ENCONTRADO")
        self.assertEqual(self.repository.llamadas, [])
        self.assertEqual(len(transporte.requests), 1)

    def test_08_viajes_no_disponible_503_sin_consultar_reservas(self):
        self.viajes.fallo = ServicioDependienteNoDisponibleError()
        self.comprobarError(self.consultar(), 503, "SERVICIO_DEPENDIENTE_NO_DISPONIBLE")
        self.assertEqual(self.repository.llamadas, [])
        self.assertEqual(self.eventos, ["viajes"])

    def test_09_servicio_defiende_dueno_e_identidad_de_cliente_sustituido(self):
        original = self.viajes.datos[305]
        for cambios, status, codigo in (
            ({"conductorId": 26}, 403, "NO_AUTORIZADO"),
            ({"viajeId": 306}, 503, "SERVICIO_DEPENDIENTE_NO_DISPONIBLE"),
        ):
            with self.subTest(cambios=cambios):
                self.viajes.datos[305] = original.model_copy(update=cambios)
                self.comprobarError(self.consultar(), status, codigo)
                self.assertEqual(self.repository.llamadas, [])

    def test_10_id_y_estado_invalidos_400_sin_lecturas(self):
        for viajeId in (0, -1, "abc", "1.5", "true"):
            with self.subTest(viajeId=viajeId):
                body = self.comprobarError(self.consultar(viajeId), 400)
                self.assertTrue(any(detalle["campo"] == "viajeId" for detalle in body["detalles"]))
        for estado in ("", "confirmada", "TODOS", "CONFIRMADA ", DATO_PRIVADO):
            with self.subTest(estado=estado):
                body = self.comprobarError(self.consultar(estado=estado), 400)
                self.assertTrue(any(detalle["campo"] == "estado" for detalle in body["detalles"]))
        self.assertEqual(self.repository.llamadas, [])
        self.assertEqual(self.viajes.llamadas, [])

    def test_11_correlacion_invalida_400_no_alcanza_servicio(self):
        for valor in ("", "invalido"):
            with self.subTest(valor=valor):
                response = self.consultar(headers=self.headers(**{"X-Correlation-Id": valor}))
                body = self.comprobarError(response, 400, "FORMATO_INVALIDO")
                self.assertTrue(any(detalle["campo"] == "X-Correlation-Id" for detalle in body["detalles"]))
        self.assertEqual(self.repository.llamadas, [])
        self.assertEqual(self.viajes.llamadas, [])

    def test_12_correlacion_se_genera_y_propaga_canonica_a_viajes(self):
        for valor in (None, str(uuid4()).upper()):
            with self.subTest(header=valor is not None):
                headers = self.headers()
                if valor is not None:
                    headers["X-Correlation-Id"] = valor
                with capturarLogs() as captura:
                    response = self.consultar(headers=headers)
                self.comprobarListado(response, 305, [1, 2, 3])
                correlationId = self.comprobarCorrelacion(response)
                if valor is not None:
                    self.assertEqual(correlationId, str(UUID(valor)))
                self.assertEqual(self.viajes.llamadas[-1][2], correlationId)
                self.assertTrue(captura.registros)
                self.assertTrue(all(getattr(record, "correlationId", None) == correlationId
                                    for record in captura.registros))
                self.assertIsNone(getCorrelationId())

    def test_13_error_sql_500_controlado_sin_sql_parametros_nombres_o_tokens(self):
        self.repository.fallo = StatementError(
            DATO_PRIVADO, "SELECT pasajero_nombre FROM dbo.reservas WHERE viaje_id = :viaje_id",
            {"pasajero_nombre": "Laura Gómez", "viaje_id": 305}, RuntimeError(DATO_PRIVADO),
        )
        token = self.emitirToken()
        with capturarLogs() as captura:
            response = self.consultar(headers={"Authorization": "Bearer " + token}, privado=DATO_PRIVADO)
        self.comprobarError(response, 500, "ERROR_INTERNO")
        self.assertEqual(self.eventos, ["viajes", "reservas"])
        contenidoLogs = "\n".join(record.getMessage() for record in captura.registros)
        for privado in (DATO_PRIVADO, "SELECT", "pasajero_nombre", "Laura Gómez", "David Ruiz",
                        "Carlos Pérez", token, self.secret.get_secret_value()):
            self.assertNotIn(privado, response.text)
            self.assertNotIn(privado, contenidoLogs)
        self.assertTrue(all(record.exc_info is None for record in captura.registros))
        self.assertTrue(all(getattr(record, "correlationId", None) == response.headers["X-Correlation-Id"]
                            for record in captura.registros))

    def test_14_metodos_de_escritura_y_rutas_no_contractuales_no_ejecutan_servicio(self):
        for metodo in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(metodo=metodo):
                response = self.client.request(metodo, "/api/v1/reservas/viaje/305", headers=self.headers())
                self.assertEqual(response.status_code, 405)
                self.assertEqual(set(response.json()), {"detail"})
                self.comprobarCorrelacion(response)
        self.assertEqual(self.client.get("/api/v1/reservas", headers=self.headers()).status_code, 404)
        self.assertEqual(self.repository.llamadas, [])
        self.assertEqual(self.viajes.llamadas, [])

    def test_15_http_integrado_solo_get_viajes_con_jwt_y_misma_correlacion(self):
        transporte = self.usarClienteViajesReal()
        token = self.emitirToken()
        correlationId = str(uuid4())
        response = self.consultar(headers={
            "Authorization": "Bearer " + token, "X-Correlation-Id": correlationId,
        })
        self.comprobarListado(response, 305, [1, 2, 3])
        self.assertEqual(len(transporte.requests), 1)
        request = transporte.requests[0]
        self.assertEqual((request.method, request.url.host, request.url.path),
                         ("GET", "viajes.test", "/api/v1/viajes/305"))
        self.assertEqual(request.headers["Authorization"], "Bearer " + token)
        self.assertEqual(request.headers["X-Correlation-Id"], correlationId)
        self.assertNotIn("X-Service-Key", request.headers)
        self.assertEqual(response.headers["X-Correlation-Id"], correlationId)
        self.assertEqual(self.repository.llamadas, [(305, None)])

    def comprobarConsulta(self, session: SesionSimulada):
        self.assertEqual(len(session.consultas), 1)
        consulta = session.consultas[0]
        self.assertTrue(consulta.is_select)
        self.assertEqual([tabla.fullname for tabla in consulta.get_final_froms()], ["dbo.reservas"])
        compilada = consulta.compile(dialect=mssql.dialect())
        sql = str(compilada)
        self.assertIn("WHERE dbo.reservas.viaje_id =", sql)
        self.assertRegex(sql, r"ORDER BY dbo\.reservas\.id(?: ASC)?\s*$")
        self.assertNotIn("305", sql)
        for palabra in (" JOIN ", "INSERT ", "UPDATE ", "DELETE ", "CREATE "):
            self.assertNotIn(palabra, sql.upper())
        self.assertEqual(session.mutaciones, [])
        return sql, compilada.params

    def test_16_repositorio_select_parametrizado_solo_tabla_propia_orden_id(self):
        datos = crearReservasEjemplo()
        session = SesionSimulada(datos)
        resultado = ReservaRepository(session).listarPorViaje(305)
        self.assertEqual(resultado, datos)
        self.assertIsNot(resultado, session.datos)
        sql, parametros = self.comprobarConsulta(session)
        self.assertEqual(list(parametros.values()), [305])
        self.assertNotIn("AND dbo.reservas.estado =", sql)

    def test_17_repositorio_filtra_cada_estado_por_parametro_sin_mutaciones(self):
        for estado in EstadoReserva:
            with self.subTest(estado=estado):
                session = SesionSimulada()
                self.assertEqual(ReservaRepository(session).listarPorViaje(305, estado), [])
                sql, parametros = self.comprobarConsulta(session)
                self.assertIn("AND dbo.reservas.estado =", sql)
                self.assertEqual(set(parametros.values()), {305, estado.value})
                self.assertNotIn(estado.value, sql)

    def test_18_repositorio_devuelve_vacio_o_propaga_fallo_sin_escrituras(self):
        session = SesionSimulada()
        self.assertEqual(ReservaRepository(session).listarPorViaje(305), [])
        self.comprobarConsulta(session)
        fallo = SQLAlchemyError(DATO_PRIVADO)
        session = SesionSimulada(fallo=fallo)
        with self.assertRaises(SQLAlchemyError) as recibido:
            ReservaRepository(session).listarPorViaje(305)
        self.assertIs(recibido.exception, fallo)
        self.comprobarConsulta(session)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VerificacionReservasViaje)
    resultado = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if resultado.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
