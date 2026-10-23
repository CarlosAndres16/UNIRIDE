"""Pruebas JWT locales con claves efímeras; no leen .env ni consultan servicios."""

from tests.contrato import RUTAS_CONTRATO

import base64
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, is_dataclass
from datetime import datetime, timedelta
import json
import logging
import os
import secrets
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import Depends
from fastapi.testclient import TestClient
import jwt
from pydantic import SecretStr, ValidationError

from app.config.settings import JwtSettings
from app.exceptions.exceptions import NoAutenticadoError, NoAutorizadoError
from app.main import app as aplicacionProduccion, crearAplicacion
from app.security.jwt_service import (
    ConductorAutenticado,
    JwtService,
    getConductorAutenticado,
    getJwtService,
    verificarPropietario,
)

HEADER_CORRELACION = "X-Correlation-Id"
CLAIM_PRIVADO = "SUB_PRIVADO_NO_PUBLICAR_9CB38D"
ERROR_PRIVADO = "CONFIGURACION_PRIVADA_NO_PUBLICAR_A73410"


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


class VerificacionJwt(unittest.TestCase):
    def setUp(self) -> None:
        # Ambas claves se generan en memoria y se descartan al terminar la prueba.
        self.secret = SecretStr(secrets.token_urlsafe(64))
        self.otraSecret = SecretStr(secrets.token_urlsafe(64))
        self.service = JwtService(self.secret)
        self.application = crearAplicacion()
        self.application.dependency_overrides[getJwtService] = lambda: self.service

        @self.application.get("/pruebas/jwt/conductor")
        async def consultarConductor(
            conductor: ConductorAutenticado = Depends(getConductorAutenticado),
        ):
            return {"conductorId": conductor.conductorId}

        @self.application.get("/pruebas/jwt/propietario/{conductorIdRecurso}")
        async def consultarRecurso(
            conductorIdRecurso: int,
            conductor: ConductorAutenticado = Depends(getConductorAutenticado),
        ):
            verificarPropietario(conductorIdRecurso, conductor)
            return {"conductorId": conductor.conductorId}

        self.client = self.enterContext(
            TestClient(self.application, raise_server_exceptions=True)
        )

    def claimsValidos(self) -> dict:
        ahora = int(time.time())
        return {"sub": "25", "iat": ahora - 5, "exp": ahora + 3600}

    def emitirToken(self, claims: dict | None = None, algoritmo: str = "HS256", secret: SecretStr | None = None) -> str:
        return jwt.encode(
            self.claimsValidos() if claims is None else claims,
            (secret or self.secret).get_secret_value(),
            algorithm=algoritmo,
        )

    def comprobarRechazo(self, token: str) -> None:
        with self.assertRaises(NoAutenticadoError) as raised:
            self.service.validarToken(token)
        error = raised.exception
        self.assertEqual(error.status, 401)
        self.assertEqual(error.error.value, "NO_AUTENTICADO")
        for privado in (token, self.secret.get_secret_value(), CLAIM_PRIVADO):
            if privado:
                self.assertNotIn(privado, str(error))

    def comprobarErrorHttp(self, response, status: int, codigo: str) -> dict:
        self.assertEqual(response.status_code, status)
        body = response.json()
        self.assertEqual(
            set(body), {"timestamp", "status", "error", "message", "path", "correlationId"}
        )
        self.assertEqual(body["status"], status)
        self.assertEqual(body["error"], codigo)
        self.assertEqual(body["path"], response.request.url.path)
        self.assertEqual(str(UUID(body["correlationId"])), body["correlationId"])
        self.assertEqual(response.headers.get(HEADER_CORRELACION), body["correlationId"])
        self.assertTrue(body["timestamp"].endswith("Z"))
        timestamp = datetime.fromisoformat(body["timestamp"].replace("Z", "+00:00"))
        self.assertEqual(timestamp.utcoffset(), timedelta(0))
        if status == 401:
            self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")
        for privado in (self.secret.get_secret_value(), CLAIM_PRIVADO, ERROR_PRIVADO):
            self.assertNotIn(privado, response.text)
        return body

    def test_configuracion_jwt_usa_secretstr_sin_variables_sql(self) -> None:
        rawSecret = self.secret.get_secret_value()
        self.assertGreaterEqual(len(rawSecret.encode("utf-8")), 32)
        with patch.dict(os.environ, {}, clear=True):
            configuracion = JwtSettings(_env_file=None, JWT_SECRET=rawSecret)
        self.assertIsInstance(configuracion.jwtSecret, SecretStr)
        self.assertEqual(configuracion.jwtSecret.get_secret_value(), rawSecret)
        self.assertNotIn(rawSecret, repr(configuracion))
        self.assertEqual(str(configuracion.jwtSecret), "**********")

    def test_configuracion_rechaza_secreto_ausente_vacio_o_espacios(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                JwtSettings(_env_file=None)
            for value in ("", " ", "\t\r\n"):
                with self.subTest(vacio=value == ""):
                    with self.assertRaises(ValidationError):
                        JwtSettings(_env_file=None, JWT_SECRET=value)

    def test_token_valido_identifica_conductor_y_oculta_token(self) -> None:
        token = self.emitirToken()
        conductor = self.service.validarToken(token)
        self.assertIsInstance(conductor, ConductorAutenticado)
        self.assertTrue(is_dataclass(conductor))
        self.assertEqual(conductor.conductorId, 25)
        self.assertIsInstance(conductor.token, SecretStr)
        self.assertEqual(conductor.token.get_secret_value(), token)
        self.assertEqual(str(conductor.token), "**********")
        self.assertNotIn(token, repr(conductor))
        self.assertNotIn("token=", repr(conductor))
        self.assertNotIn(self.secret.get_secret_value(), repr(self.service))
        with self.assertRaises(FrozenInstanceError):
            conductor.conductorId = 26

    def test_consumidor_no_impone_duracion_maxima_de_3600_segundos(self) -> None:
        ahora = int(time.time())
        token = self.emitirToken({"sub": "25", "iat": ahora - 7200, "exp": ahora + 7200})
        self.assertEqual(self.service.validarToken(token).conductorId, 25)

    def test_no_exige_audience_issuer_ni_roles(self) -> None:
        token = self.emitirToken()
        self.assertEqual(self.service.validarToken(token).conductorId, 25)
        claims = self.claimsValidos() | {"aud": "audiencia-opcional", "iss": "emisor-opcional"}
        self.assertEqual(self.service.validarToken(self.emitirToken(claims)).conductorId, 25)

    def test_formato_firma_y_algoritmos_no_permitidos_se_rechazan(self) -> None:
        casos = {
            "formato": "token-malformado",
            "firma_ajena": self.emitirToken(secret=self.otraSecret),
            "HS384": self.emitirToken(algoritmo="HS384"),
            "none": jwt.encode(self.claimsValidos(), key=None, algorithm="none"),
        }
        for caso, token in casos.items():
            with self.subTest(caso=caso):
                self.comprobarRechazo(token)

    def test_manipulacion_del_payload_invalida_la_firma(self) -> None:
        header, payload, firma = self.emitirToken().split(".")
        decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        decoded["sub"] = "99"
        payloadManipulado = base64.urlsafe_b64encode(
            json.dumps(decoded, separators=(",", ":")).encode("utf-8")
        ).rstrip(b"=").decode("ascii")
        self.comprobarRechazo(".".join((header, payloadManipulado, firma)))

    def test_sub_iat_y_exp_son_obligatorios(self) -> None:
        for campo in ("sub", "iat", "exp"):
            with self.subTest(campo=campo):
                claims = self.claimsValidos()
                claims.pop(campo)
                self.comprobarRechazo(self.emitirToken(claims))

    def test_sub_debe_ser_texto_decimal_ascii_positivo(self) -> None:
        valores = (
            "0", "000", "-25", "+25", " 25", "25 ", "25.0", "25\n", "",
            "٢٥", "２５", CLAIM_PRIVADO, 25, 25.0, True, None, ["25"], {"id": "25"},
        )
        for valor in valores:
            with self.subTest(tipo=type(valor).__name__, valor=repr(valor)):
                self.comprobarRechazo(self.emitirToken(self.claimsValidos() | {"sub": valor}))

    def test_iat_y_exp_rechazan_coercion_de_strings_bool_y_decimales(self) -> None:
        claims = self.claimsValidos()
        for campo in ("iat", "exp"):
            for valor in (str(claims[campo]), float(claims[campo]), True, False, None, [], {}):
                with self.subTest(campo=campo, tipo=type(valor).__name__):
                    self.comprobarRechazo(self.emitirToken(claims | {campo: valor}))

    def test_iat_futuro_se_rechaza(self) -> None:
        ahora = int(time.time())
        self.comprobarRechazo(self.emitirToken({"sub": "25", "iat": ahora + 300, "exp": ahora + 3600}))

    def test_token_vencido_y_periodo_exp_menor_o_igual_iat_se_rechazan(self) -> None:
        ahora = int(time.time())
        casos = (
            {"sub": "25", "iat": ahora - 3600, "exp": ahora - 1},
            {"sub": "25", "iat": ahora - 5, "exp": ahora - 5},
            {"sub": "25", "iat": ahora - 5, "exp": ahora - 6},
        )
        for indice, claims in enumerate(casos):
            with self.subTest(caso=indice):
                self.comprobarRechazo(self.emitirToken(claims))

    def test_http_valido_con_depends_y_correlacion_canonica(self) -> None:
        token = self.emitirToken()
        correlationId = str(uuid4())
        response = self.client.get(
            "/pruebas/jwt/conductor",
            headers={"Authorization": "bEaReR " + token, HEADER_CORRELACION: correlationId.upper()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"conductorId": 25})
        self.assertEqual(response.headers.get(HEADER_CORRELACION), correlationId)
        self.assertNotIn(token, response.text)

    def test_http_bearer_con_varios_espacios_es_valido(self) -> None:
        response = self.client.get(
            "/pruebas/jwt/conductor",
            headers={"Authorization": "bEaReR  " + self.emitirToken()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"conductorId": 25})

    def test_http_authorization_ausente_basic_o_bearer_vacio_es_401(self) -> None:
        headers = (
            {},
            {"Authorization": ""},
            {"Authorization": "Basic Y29uZHVjdG9yOnBydWViYQ=="},
            {"Authorization": "Bearer"},
            {"Authorization": "Bearer "},
            {"Authorization": "Bearer " + self.emitirToken() + " adicional"},
        )
        for indice, authorization in enumerate(headers):
            with self.subTest(caso=indice):
                response = self.client.get("/pruebas/jwt/conductor", headers=authorization)
                self.comprobarErrorHttp(response, 401, "NO_AUTENTICADO")

    def test_http_authorization_duplicado_es_401(self) -> None:
        authorization = "Bearer " + self.emitirToken()
        response = self.client.get(
            "/pruebas/jwt/conductor",
            headers=[("Authorization", authorization), ("Authorization", authorization)],
        )
        self.comprobarErrorHttp(response, 401, "NO_AUTENTICADO")

    def test_http_token_invalido_es_401_generico_sin_datos_del_claim(self) -> None:
        token = self.emitirToken(self.claimsValidos() | {"sub": CLAIM_PRIVADO})
        correlationId = str(uuid4())
        response = self.client.get(
            "/pruebas/jwt/conductor",
            headers={"Authorization": "Bearer " + token, HEADER_CORRELACION: correlationId},
        )
        body = self.comprobarErrorHttp(response, 401, "NO_AUTENTICADO")
        self.assertEqual(body["correlationId"], correlationId)
        self.assertNotIn(token, response.text)

    def test_propietario_igual_pasa_y_propietario_ajeno_es_403(self) -> None:
        conductor = self.service.validarToken(self.emitirToken())
        self.assertIsNone(verificarPropietario(25, conductor))
        with self.assertRaises(NoAutorizadoError) as raised:
            verificarPropietario(26, conductor)
        self.assertEqual(raised.exception.status, 403)
        self.assertEqual(raised.exception.error.value, "NO_AUTORIZADO")

    def test_propietario_booleano_no_equivale_a_conductor_uno(self) -> None:
        conductor = self.service.validarToken(self.emitirToken(self.claimsValidos() | {"sub": "1"}))
        self.assertEqual(conductor.conductorId, 1)
        with self.assertRaises(NoAutorizadoError) as raised:
            verificarPropietario(True, conductor)
        self.assertEqual(raised.exception.status, 403)

    def test_http_recurso_ajeno_es_403_y_propio_es_200(self) -> None:
        headers = {"Authorization": "Bearer " + self.emitirToken()}
        self.assertEqual(
            self.client.get("/pruebas/jwt/propietario/25", headers=headers).status_code, 200
        )
        response = self.client.get("/pruebas/jwt/propietario/26", headers=headers)
        self.comprobarErrorHttp(response, 403, "NO_AUTORIZADO")

    def test_provider_con_secreto_vacio_es_500_sin_leer_env(self) -> None:
        self.application.dependency_overrides.pop(getJwtService)
        for value in ("", " \t\n"):
            with self.subTest(vacio=value == ""):
                with patch(
                    "app.security.jwt_service.getJwtSettings",
                    return_value=SimpleNamespace(jwtSecret=SecretStr(value)),
                ) as proveedor:
                    response = self.client.get(
                        "/pruebas/jwt/conductor",
                        headers={"Authorization": "Bearer " + self.emitirToken()},
                    )
                proveedor.assert_called_once_with()
                self.comprobarErrorHttp(response, 500, "ERROR_INTERNO")

    def test_provider_no_revela_excepcion_privada_de_configuracion(self) -> None:
        self.application.dependency_overrides.pop(getJwtService)
        with patch(
            "app.security.jwt_service.getJwtSettings",
            side_effect=ValueError(ERROR_PRIVADO),
        ):
            with capturarLogs() as captura:
                response = self.client.get(
                    "/pruebas/jwt/conductor",
                    headers={"Authorization": "Bearer " + self.emitirToken()},
                )
        self.comprobarErrorHttp(response, 500, "ERROR_INTERNO")
        self.assertTrue(captura.registros)
        for record in captura.registros:
            self.assertNotIn(ERROR_PRIVADO, record.getMessage())
            self.assertIsNone(record.exc_info)

    def test_authorization_ausente_no_carga_configuracion_jwt(self) -> None:
        self.application.dependency_overrides.pop(getJwtService)
        with patch(
            "app.security.jwt_service.getJwtSettings",
            side_effect=AssertionError("La autenticación ausente no debe cargar el secreto."),
        ) as proveedor:
            response = self.client.get("/pruebas/jwt/conductor")
        proveedor.assert_not_called()
        self.comprobarErrorHttp(response, 401, "NO_AUTENTICADO")

    def test_logs_no_registran_token_secreto_claim_ni_excepcion_privada(self) -> None:
        tokenValido = self.emitirToken()
        tokenInvalido = self.emitirToken(self.claimsValidos() | {"sub": CLAIM_PRIVADO})
        correlationIds = [str(uuid4()), str(uuid4())]
        with capturarLogs() as captura:
            valido = self.client.get(
                "/pruebas/jwt/conductor",
                headers={"Authorization": "Bearer " + tokenValido, HEADER_CORRELACION: correlationIds[0]},
            )
            invalido = self.client.get(
                "/pruebas/jwt/conductor",
                headers={"Authorization": "Bearer " + tokenInvalido, HEADER_CORRELACION: correlationIds[1]},
            )
        self.assertEqual(valido.status_code, 200)
        self.comprobarErrorHttp(invalido, 401, "NO_AUTENTICADO")
        self.assertGreaterEqual(len(captura.registros), 2)
        idsRegistrados = set()
        for record in captura.registros:
            correlationId = getattr(record, "correlationId", None)
            self.assertIn(correlationId, correlationIds)
            idsRegistrados.add(correlationId)
            self.assertIsNone(record.exc_info)
            for privado in (tokenValido, tokenInvalido, self.secret.get_secret_value(), CLAIM_PRIVADO, ERROR_PRIVADO):
                self.assertNotIn(privado, record.getMessage())
        self.assertEqual(idsRegistrados, set(correlationIds))

    def test_validacion_local_no_llama_sql_ni_clientes_http_externos(self) -> None:
        with (
            patch("app.config.database.getEngine", side_effect=AssertionError("No usar SQL.")) as engine,
            patch("app.config.database.getSessionFactory", side_effect=AssertionError("No usar SQL.")) as sesiones,
            patch("httpx.AsyncClient.request", side_effect=AssertionError("No llamar servicios.")) as http,
        ):
            token = self.emitirToken()
            self.assertEqual(self.service.validarToken(token).conductorId, 25)
            response = self.client.get(
                "/pruebas/jwt/conductor", headers={"Authorization": "Bearer " + token}
            )
        self.assertEqual(response.status_code, 200)
        engine.assert_not_called()
        sesiones.assert_not_called()
        http.assert_not_called()

    def test_produccion_solo_expone_reservas_por_viaje_protegidas(self) -> None:
        with TestClient(aplicacionProduccion, raise_server_exceptions=True) as client:
            response = client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertEqual(set(paths), RUTAS_CONTRATO)
        self.assertEqual(set(paths["/api/v1/reservas/viaje/{viajeId}"]), {"get"})
        self.assertEqual(paths["/api/v1/reservas/viaje/{viajeId}"]["get"]["security"], [{"BearerAuth": []}])


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(VerificacionJwt)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
