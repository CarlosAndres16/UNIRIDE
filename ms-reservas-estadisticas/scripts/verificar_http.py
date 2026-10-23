"""Verificación HTTP reproducible de la fase 5, sin conexiones de red ni SQL."""

from tests.contrato import RUTAS_CONTRATO

import asyncio
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import logging
import traceback
import unittest
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config.logging_config import CorrelationIdFilter, configurarLogging
from app.exceptions.exceptions import ExcepcionAplicacion
from app.main import app as aplicacionProduccion, crearAplicacion
from app.middleware.correlation_id import (
    CorrelationIdMiddleware,
    ErrorRespuestaIniciada,
    getCorrelationId,
)
from app.schemas.error_schema import CodigoError, ErrorResponse

HEADER_CORRELACION = "X-Correlation-Id"
MENSAJE_PRIVADO = "EXCEPCION_PRIVADA_NO_PUBLICAR_57F49A"
TOKEN_PRIVADO = "TOKEN_PRIVADO_NO_REGISTRAR_32B897"
QUERY_PRIVADA = "QUERY_PRIVADA_NO_REGISTRAR_F4CC51"
CUERPO_PRIVADO = "CUERPO_PRIVADO_NO_REGISTRAR_D1227C"


class DatosPrueba(BaseModel):
    numero: int


class CapturaLogs(logging.Handler):
    """Recoge únicamente logs sintéticos de estas comprobaciones."""

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


def endpointError(error: Exception):
    async def responder():
        raise error

    return responder


class VerificacionHttp(unittest.TestCase):
    def setUp(self) -> None:
        self.application = crearAplicacion()
        self.client = self.enterContext(
            TestClient(self.application, raise_server_exceptions=True)
        )

    def comprobarCorrelacion(self, response: httpx.Response) -> str:
        correlationId = response.headers.get(HEADER_CORRELACION)
        self.assertIsNotNone(correlationId)
        self.assertEqual(str(UUID(correlationId)), correlationId)
        return correlationId

    def comprobarError(
        self,
        response: httpx.Response,
        status: int,
        error: CodigoError,
    ) -> dict:
        self.assertEqual(response.status_code, status)
        correlationId = self.comprobarCorrelacion(response)
        body = response.json()
        campos = {"timestamp", "status", "error", "message", "path", "correlationId"}
        if status == 400:
            campos.add("detalles")
            self.assertIsInstance(body.get("detalles"), list)
            for detalle in body["detalles"]:
                self.assertEqual(set(detalle), {"campo", "problema"})
                self.assertIsInstance(detalle["campo"], str)
                self.assertIsInstance(detalle["problema"], str)
        self.assertEqual(set(body), campos)
        self.assertEqual(body["status"], status)
        self.assertEqual(body["error"], error.value)
        self.assertEqual(body["path"], response.request.url.path)
        self.assertEqual(body["correlationId"], correlationId)
        self.assertIsInstance(body["message"], str)
        self.assertTrue(body["message"].strip())
        self.assertTrue(body["timestamp"].endswith("Z"))
        timestamp = datetime.fromisoformat(body["timestamp"].replace("Z", "+00:00"))
        self.assertEqual(timestamp.utcoffset(), timedelta(0))
        ErrorResponse.model_validate(body)
        return body

    def test_docs_genera_uuid(self) -> None:
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("swagger-ui", response.text)
        self.comprobarCorrelacion(response)

    def test_uuid_valido_se_conserva_canonico(self) -> None:
        correlationId = str(uuid4())
        response = self.client.get(
            "/docs", headers={HEADER_CORRELACION: correlationId.upper()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.comprobarCorrelacion(response), correlationId)

    def test_uuid_invalido_o_vacio_produce_400(self) -> None:
        for valor in ("uuid-invalido", ""):
            with self.subTest(header=valor):
                response = self.client.get("/docs", headers={HEADER_CORRELACION: valor})
                body = self.comprobarError(response, 400, CodigoError.FORMATO_INVALIDO)
                self.assertTrue(body["detalles"])
                self.assertEqual(body["detalles"][0]["campo"], HEADER_CORRELACION)

    def test_uuid_duplicado_produce_400_con_uuid_nuevo(self) -> None:
        primerId = str(uuid4())
        for segundoId in (primerId, str(uuid4())):
            with self.subTest(duplicadoIgual=primerId == segundoId):
                response = self.client.get(
                    "/docs",
                    headers=[
                        (HEADER_CORRELACION, primerId),
                        (HEADER_CORRELACION, segundoId),
                    ],
                )
                body = self.comprobarError(response, 400, CodigoError.FORMATO_INVALIDO)
                self.assertNotIn(body["correlationId"], (primerId, segundoId))
                self.assertTrue(body["detalles"])
                self.assertEqual(body["detalles"][0]["campo"], HEADER_CORRELACION)

    def test_errores_dominio_respetan_contrato(self) -> None:
        casos = (
            (400, CodigoError.SOLICITUD_INVALIDA),
            (400, CodigoError.CAMPO_OBLIGATORIO_FALTANTE),
            (400, CodigoError.FORMATO_INVALIDO),
            (400, CodigoError.FECHA_HORA_INVALIDA),
            (400, CodigoError.CAPACIDAD_INVALIDA),
            (401, CodigoError.NO_AUTENTICADO),
            (403, CodigoError.NO_AUTORIZADO),
            (404, CodigoError.VIAJE_NO_ENCONTRADO),
            (404, CodigoError.RESERVA_NO_ENCONTRADA),
            (404, CodigoError.VEHICULO_NO_ENCONTRADO),
            (503, CodigoError.SERVICIO_DEPENDIENTE_NO_DISPONIBLE),
        )
        for status, codigo in casos:
            with self.subTest(status=status, error=codigo):
                path = f"/pruebas/error/{codigo.value.lower()}"
                self.application.add_api_route(
                    path,
                    endpointError(ExcepcionAplicacion(status, codigo, "Mensaje público controlado.")),
                    methods=["GET"],
                )
                correlationId = str(uuid4())
                response = self.client.get(path, headers={HEADER_CORRELACION: correlationId})
                body = self.comprobarError(response, status, codigo)
                self.assertEqual(body["correlationId"], correlationId)
                if status == 400:
                    self.assertEqual(body["detalles"], [])

    def test_error_400_preserva_detalles_controlados(self) -> None:
        detalles = [{"campo": "desde", "problema": "No puede ser posterior a hasta."}]
        self.application.add_api_route(
            "/pruebas/detalles",
            endpointError(ExcepcionAplicacion(
                400, CodigoError.SOLICITUD_INVALIDA, "Periodo inválido.", detalles=detalles
            )),
            methods=["GET"],
        )
        body = self.comprobarError(
            self.client.get("/pruebas/detalles"), 400, CodigoError.SOLICITUD_INVALIDA
        )
        self.assertEqual(body["detalles"], detalles)

    def test_validacion_campo_obligatorio_es_400(self) -> None:
        @self.application.get("/pruebas/obligatorio")
        async def obligatorio(valor: int):
            return {"valor": valor}

        body = self.comprobarError(
            self.client.get("/pruebas/obligatorio"),
            400,
            CodigoError.CAMPO_OBLIGATORIO_FALTANTE,
        )
        self.assertEqual(body["detalles"][0]["campo"], "valor")

    def test_validacion_entero_es_400_sin_input(self) -> None:
        @self.application.get("/pruebas/entero")
        async def entero(valor: int):
            return {"valor": valor}

        valorPrivado = "VALOR_PRIVADO_ENTERO_79B34F"
        response = self.client.get("/pruebas/entero", params={"valor": valorPrivado})
        self.comprobarError(response, 400, CodigoError.FORMATO_INVALIDO)
        self.assertNotIn(valorPrivado, response.text)
        self.assertNotIn('"input"', response.text)

    def test_validacion_fecha_es_400_sin_input(self) -> None:
        @self.application.get("/pruebas/fecha")
        async def fecha(desde: date):
            return {"desde": desde.isoformat()}

        valorPrivado = "VALOR_PRIVADO_FECHA_7115D0"
        response = self.client.get("/pruebas/fecha", params={"desde": valorPrivado})
        self.comprobarError(response, 400, CodigoError.FECHA_HORA_INVALIDA)
        self.assertNotIn(valorPrivado, response.text)
        self.assertNotIn('"input"', response.text)

    def test_validacion_json_es_400_sin_cuerpo_original(self) -> None:
        @self.application.post("/pruebas/json")
        async def recibirJson(datos: DatosPrueba):
            return {"numero": datos.numero}

        response = self.client.post(
            "/pruebas/json",
            content='{"numero": "' + CUERPO_PRIVADO + '"',
            headers={"Content-Type": "application/json"},
        )
        body = self.comprobarError(response, 400, CodigoError.FORMATO_INVALIDO)
        self.assertEqual(body["detalles"][0]["campo"], "body")
        self.assertNotIn(CUERPO_PRIVADO, response.text)
        self.assertNotIn('"input"', response.text)

    def test_validacion_modelo_es_400_sin_valor_privado(self) -> None:
        @self.application.post("/pruebas/modelo")
        async def recibirModelo(datos: DatosPrueba):
            return {"numero": datos.numero}

        response = self.client.post("/pruebas/modelo", json={"numero": CUERPO_PRIVADO})
        body = self.comprobarError(response, 400, CodigoError.FORMATO_INVALIDO)
        self.assertEqual(body["detalles"][0]["campo"], "numero")
        self.assertNotIn(CUERPO_PRIVADO, response.text)
        self.assertNotIn('"input"', response.text)

    def test_excepcion_inesperada_es_500_publico(self) -> None:
        self.application.add_api_route(
            "/pruebas/inesperado", endpointError(RuntimeError(MENSAJE_PRIVADO)), methods=["GET"]
        )
        correlationId = str(uuid4())
        response = self.client.get(
            "/pruebas/inesperado",
            params={"dato": QUERY_PRIVADA},
            headers={HEADER_CORRELACION: correlationId, "Authorization": "Bearer " + TOKEN_PRIVADO},
        )
        body = self.comprobarError(response, 500, CodigoError.ERROR_INTERNO)
        self.assertEqual(body["correlationId"], correlationId)
        for privado in (MENSAJE_PRIVADO, QUERY_PRIVADA, TOKEN_PRIVADO):
            self.assertNotIn(privado, response.text)

    def test_logs_tienen_correlacion_y_omiten_datos_privados(self) -> None:
        @self.application.post("/pruebas/logs")
        async def registrarActividad():
            logging.getLogger("uniride.pruebas").info("Actividad sintética de verificación.")
            return {"ok": True}

        self.application.add_api_route(
            "/pruebas/logs/error", endpointError(RuntimeError(MENSAJE_PRIVADO)), methods=["GET"]
        )
        correlationIds = [str(uuid4()), str(uuid4())]
        with capturarLogs() as captura:
            response = self.client.post(
                "/pruebas/logs",
                params={"dato": QUERY_PRIVADA},
                content=CUERPO_PRIVADO,
                headers={
                    HEADER_CORRELACION: correlationIds[0],
                    "Authorization": "Bearer " + TOKEN_PRIVADO,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.comprobarError(
                self.client.get(
                    "/pruebas/logs/error", headers={HEADER_CORRELACION: correlationIds[1]}
                ),
                500,
                CodigoError.ERROR_INTERNO,
            )

        self.assertGreaterEqual(len(captura.registros), 2)
        idsRegistrados = set()
        for record in captura.registros:
            correlationId = getattr(record, "correlationId", None)
            self.assertIn(correlationId, correlationIds)
            idsRegistrados.add(correlationId)
            self.assertIsNone(record.exc_info)
            message = record.getMessage()
            for privado in (MENSAJE_PRIVADO, TOKEN_PRIVADO, QUERY_PRIVADA, CUERPO_PRIVADO):
                self.assertNotIn(privado, message)
        self.assertEqual(idsRegistrados, set(correlationIds))

    def test_filtro_fuera_de_solicitud_no_reutiliza_uuid(self) -> None:
        self.assertIsNone(getCorrelationId())
        configurarLogging()
        filtro = CorrelationIdFilter()
        record = logging.LogRecord("uniride.pruebas", logging.INFO, __file__, 0, "Verificación", (), None)
        self.assertTrue(filtro.filter(record))
        self.assertEqual(record.correlationId, "-")
        correlationId = str(uuid4())
        record.correlationId = correlationId
        self.assertTrue(filtro.filter(record))
        self.assertEqual(record.correlationId, correlationId)

    def test_diez_solicitudes_concurrentes_no_mezclan_uuid(self) -> None:
        @self.application.get("/pruebas/concurrencia")
        async def observarContexto():
            antes = getCorrelationId()
            await asyncio.sleep(0.01)
            return {"antes": antes, "despues": getCorrelationId()}

        async def verificar():
            self.assertIsNone(getCorrelationId())
            transport = httpx.ASGITransport(app=self.application, raise_app_exceptions=True)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                correlationIds = [str(uuid4()) for _ in range(10)]
                responses = await asyncio.gather(*(
                    client.get("/pruebas/concurrencia", headers={HEADER_CORRELACION: correlationId})
                    for correlationId in correlationIds
                ))
                for correlationId, response in zip(correlationIds, responses, strict=True):
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(self.comprobarCorrelacion(response), correlationId)
                    self.assertEqual(response.json(), {"antes": correlationId, "despues": correlationId})
            self.assertIsNone(getCorrelationId())

        asyncio.run(verificar())

    def test_contexto_se_resetea_en_exito_y_errores(self) -> None:
        self.application.add_api_route(
            "/pruebas/contexto/dominio",
            endpointError(ExcepcionAplicacion(403, CodigoError.NO_AUTORIZADO, "Acceso denegado.")),
            methods=["GET"],
        )
        self.application.add_api_route(
            "/pruebas/contexto/error", endpointError(RuntimeError(MENSAJE_PRIVADO)), methods=["GET"]
        )

        async def verificar():
            self.assertIsNone(getCorrelationId())
            transport = httpx.ASGITransport(app=self.application, raise_app_exceptions=True)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                casos = (
                    ("/docs", {HEADER_CORRELACION: str(uuid4())}, 200),
                    ("/docs", {HEADER_CORRELACION: "uuid-invalido"}, 400),
                    ("/pruebas/contexto/dominio", {}, 403),
                    ("/pruebas/contexto/error", {}, 500),
                )
                for path, headers, status in casos:
                    response = await client.get(path, headers=headers)
                    self.assertEqual(response.status_code, status)
                    self.comprobarCorrelacion(response)
                    self.assertIsNone(getCorrelationId())

        asyncio.run(verificar())

    def test_produccion_expone_solo_el_get_de_reservas_por_viaje(self) -> None:
        with TestClient(aplicacionProduccion, raise_server_exceptions=True) as client:
            response = client.get("/openapi.json")
            self.assertEqual(response.status_code, 200)
            paths = response.json()["paths"]
            self.assertEqual(set(paths), RUTAS_CONTRATO)
            self.assertEqual(set(paths["/api/v1/reservas/viaje/{viajeId}"]), {"get"})
            self.comprobarCorrelacion(response)

    def test_404_y_405_de_enrutamiento_permanecen_nativos(self) -> None:
        for method, path, status, detail in (
            ("GET", "/ruta-no-definida", 404, "Not Found"),
            ("POST", "/docs", 405, "Method Not Allowed"),
        ):
            with self.subTest(status=status):
                correlationId = str(uuid4())
                response = self.client.request(method, path, headers={HEADER_CORRELACION: correlationId})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"detail": detail})
                self.assertEqual(self.comprobarCorrelacion(response), correlationId)

    def test_http_504_se_traduce_a_503(self) -> None:
        self.application.add_api_route(
            "/pruebas/timeout",
            endpointError(HTTPException(status_code=504, detail=MENSAJE_PRIVADO)),
            methods=["GET"],
        )
        response = self.client.get("/pruebas/timeout")
        self.comprobarError(response, 503, CodigoError.SERVICIO_DEPENDIENTE_NO_DISPONIBLE)
        self.assertNotIn(MENSAJE_PRIVADO, response.text)

    def test_fallo_tras_iniciar_respuesta_sanea_traceback_y_restaura_contexto(self) -> None:
        async def verificar():
            self.assertIsNone(getCorrelationId())
            correlationId = str(uuid4())
            messages = []
            scope = {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "root_path": "",
                "path": "/pruebas/respuesta-iniciada",
                "raw_path": b"/pruebas/respuesta-iniciada",
                "query_string": b"",
                "headers": [(b"x-correlation-id", correlationId.encode("ascii"))],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "state": {},
            }

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                messages.append(message)

            async def respuestaIncompleta(scope, receive, send):
                self.assertEqual(getCorrelationId(), correlationId)
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain")],
                })
                await send({
                    "type": "http.response.body", "body": b"inicio", "more_body": True
                })
                raise RuntimeError(MENSAJE_PRIVADO)

            middleware = CorrelationIdMiddleware(respuestaIncompleta)
            with capturarLogs() as captura:
                try:
                    await middleware(scope, receive, send)
                except ErrorRespuestaIniciada as error:
                    trace = "".join(traceback.format_exception(error))
                    self.assertIn(correlationId, str(error))
                    self.assertIn(correlationId, trace)
                    self.assertNotIn(MENSAJE_PRIVADO, trace)
                    self.assertIsNone(error.__cause__)
                    self.assertTrue(error.__suppress_context__)
                else:
                    self.fail("Una respuesta incompleta debe propagar un error público saneado.")

            self.assertIsNone(getCorrelationId())
            starts = [message for message in messages if message["type"] == "http.response.start"]
            self.assertEqual(len(starts), 1)
            self.assertEqual(starts[0]["status"], 200)
            headers = dict(starts[0]["headers"])
            self.assertEqual(headers[b"x-correlation-id"].decode("ascii"), correlationId)
            self.assertGreaterEqual(len(captura.registros), 1)
            for record in captura.registros:
                self.assertEqual(getattr(record, "correlationId", None), correlationId)
                self.assertNotIn(MENSAJE_PRIVADO, record.getMessage())
                self.assertIsNone(record.exc_info)

        asyncio.run(verificar())


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VerificacionHttp)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
