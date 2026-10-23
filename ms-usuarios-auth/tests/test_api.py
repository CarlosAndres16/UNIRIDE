"""Comportamiento HTTP, propiedad de recursos, privacidad y trazabilidad."""

from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.conftest import TEST_PASSWORD


PUBLIC_FIELDS = {"conductorId", "nombre", "correo", "telefono", "activo"}


def assertError(response: Any, status: int, error: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = response.json()
    assert {"timestamp", "status", "error", "message", "path", "correlationId"} <= body.keys()
    assert body["status"] == status
    assert body["error"] == error
    assert body["path"] == response.request.url.path
    assert body["correlationId"] == response.headers["X-Correlation-Id"]
    UUID(body["correlationId"])
    timestamp = datetime.fromisoformat(body["timestamp"].replace("Z", "+00:00"))
    assert timestamp.utcoffset() == timezone.utc.utcoffset(timestamp)
    if status == 400:
        assert isinstance(body["detalles"], list)
    return body


def test_registro_crea_conductor(client: TestClient, registroPayload: dict[str, Any]) -> None:
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 201
    assert response.json().keys() == PUBLIC_FIELDS
    assert response.json()["conductorId"] > 0
    assert response.json()["activo"] is True


def test_correo_se_guarda_en_minusculas(
    client: TestClient, registroPayload: dict[str, Any], dbSession: Session
) -> None:
    from app.models.conductor import Conductor

    registroPayload["correo"] = "JUAN@EXAMPLE.COM"
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 201
    assert response.json()["correo"] == "juan@example.com"
    conductor = dbSession.scalar(select(Conductor))
    assert conductor.correo == "juan@example.com"


def test_correo_duplicado_ignora_mayusculas(
    client: TestClient, conductorRegistrado: dict[str, Any], registroPayload: dict[str, Any]
) -> None:
    registroPayload["correo"] = "JUAN@EXAMPLE.COM"
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assertError(response, 409, "CORREO_YA_REGISTRADO")


@pytest.mark.parametrize("telefono", [None, "3001234567"])
def test_registro_telefono_opcional(
    client: TestClient, registroPayload: dict[str, Any], telefono: str | None
) -> None:
    registroPayload["telefono"] = telefono
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 201
    assert response.json()["telefono"] == telefono


def test_registro_admite_omitir_telefono(client: TestClient, registroPayload: dict[str, Any]) -> None:
    registroPayload.pop("telefono")
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 201
    assert response.json()["telefono"] is None


@pytest.mark.parametrize("campo", ["nombre", "correo", "password"])
def test_registro_requiere_campos_obligatorios(
    client: TestClient, registroPayload: dict[str, Any], campo: str
) -> None:
    registroPayload.pop(campo)
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assertError(response, 400, "CAMPO_OBLIGATORIO_FALTANTE")


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("nombre", ""), ("correo", "sin-arroba"), ("password", "1234567"), ("telefono", "1" * 31)],
)
def test_registro_rechaza_datos_invalidos(
    client: TestClient, registroPayload: dict[str, Any], campo: str, valor: str
) -> None:
    registroPayload[campo] = valor
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 400
    assert response.json()["detalles"]


def test_registro_password_minimo_ocho(client: TestClient, registroPayload: dict[str, Any]) -> None:
    registroPayload["password"] = "12345678"
    assert client.post("/api/v1/auth/registro", json=registroPayload).status_code == 201


def test_password_se_almacena_como_hash(
    conductorRegistrado: dict[str, Any], dbSession: Session
) -> None:
    from app.models.conductor import Conductor
    from app.security.password_service import PasswordService

    conductor = dbSession.get(Conductor, conductorRegistrado["conductorId"])
    assert conductor.password_hash != TEST_PASSWORD
    assert conductor.password_hash.startswith("$argon2id$")
    assert PasswordService().verifyPassword(TEST_PASSWORD, conductor.password_hash)


def test_password_no_aparece_en_respuesta_ni_logs(
    client: TestClient, registroPayload: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 201
    assert TEST_PASSWORD not in response.text
    assert TEST_PASSWORD not in caplog.text
    for campo in ("password", "passwordHash", "password_hash"):
        assert campo not in response.json()


def test_error_de_validacion_no_refleja_password(client: TestClient, registroPayload: dict[str, Any]) -> None:
    registroPayload["password"] = "Privado"
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assert response.status_code == 400
    assert "Privado" not in response.text
    assert "input" not in response.json().get("detalles", [{}])[0]


def test_login_correcto(autenticacion: dict[str, Any], conductorRegistrado: dict[str, Any]) -> None:
    assert autenticacion.keys() == {"accessToken", "tokenType", "expiresIn", "conductorId"}
    assert autenticacion["tokenType"] == "Bearer"
    assert autenticacion["expiresIn"] == 3600
    assert autenticacion["conductorId"] == conductorRegistrado["conductorId"]


def test_login_normaliza_correo(client: TestClient, conductorRegistrado: dict[str, Any]) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"correo": "JUAN@EXAMPLE.COM", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("correo", "password"),
    [("no-existe@example.com", TEST_PASSWORD), ("juan@example.com", "ClaveIncorrecta123!")],
)
def test_credenciales_invalidas(
    client: TestClient, conductorRegistrado: dict[str, Any], correo: str, password: str
) -> None:
    response = client.post("/api/v1/auth/login", json={"correo": correo, "password": password})
    assertError(response, 401, "CREDENCIALES_INVALIDAS")
    assert password not in response.text


def test_mensaje_login_no_revela_que_credencial_fallo(
    client: TestClient, conductorRegistrado: dict[str, Any]
) -> None:
    unknownEmail = client.post(
        "/api/v1/auth/login", json={"correo": "no-existe@example.com", "password": TEST_PASSWORD}
    )
    wrongPassword = client.post(
        "/api/v1/auth/login", json={"correo": "juan@example.com", "password": "OtraClave123!"}
    )
    assert unknownEmail.status_code == wrongPassword.status_code == 401
    assert unknownEmail.json()["message"] == wrongPassword.json()["message"]
    assert unknownEmail.json()["error"] == wrongPassword.json()["error"] == "CREDENCIALES_INVALIDAS"


def test_login_formato_invalido(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"correo": "invalido", "password": TEST_PASSWORD})
    assert response.status_code == 400


def test_me_usa_identidad_jwt(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any]
) -> None:
    response = client.get("/api/v1/auth/me", headers=authHeaders)
    assert response.status_code == 200
    assert response.json() == conductorRegistrado


def test_me_no_toma_identidad_de_query(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any]
) -> None:
    response = client.get("/api/v1/auth/me?conductorId=999999", headers=authHeaders)
    assert response.status_code == 200
    assert response.json()["conductorId"] == conductorRegistrado["conductorId"]


def test_consulta_conductor_propio(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any]
) -> None:
    response = client.get(f"/api/v1/conductores/{conductorRegistrado['conductorId']}", headers=authHeaders)
    assert response.status_code == 200
    assert response.json() == conductorRegistrado


@pytest.mark.parametrize("metodo", ["get", "put"])
def test_recurso_ajeno_prohibido(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any], metodo: str
) -> None:
    otherId = conductorRegistrado["conductorId"] + 1
    kwargs = {"headers": authHeaders}
    if metodo == "put":
        kwargs["json"] = {"nombre": "Nombre ajeno", "telefono": None}
    response = getattr(client, metodo)(f"/api/v1/conductores/{otherId}", **kwargs)
    assertError(response, 403, "NO_AUTORIZADO")
    assert TEST_PASSWORD not in response.text


@pytest.mark.parametrize("ruta", ["/api/v1/auth/me", "/api/v1/conductores/999999"])
def test_identidad_valida_sin_conductor_da_404(client: TestClient, testSettings: Any, ruta: str) -> None:
    from app.security.jwt_service import JWTService

    token = JWTService(testSettings).generarToken(999999)
    response = client.get(ruta, headers={"Authorization": f"Bearer {token}"})
    assertError(response, 404, "CONDUCTOR_NO_ENCONTRADO")


def test_actualiza_nombre_y_telefono(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any], dbSession: Session
) -> None:
    from app.models.conductor import Conductor

    conductorId = conductorRegistrado["conductorId"]
    before = dbSession.get(Conductor, conductorId)
    originalCreation = before.fecha_creacion
    originalHash = before.password_hash
    response = client.put(
        f"/api/v1/conductores/{conductorId}",
        headers=authHeaders,
        json={"nombre": "Juan Alejandro Apache", "telefono": "3010000000"},
    )
    assert response.status_code == 200
    assert response.json()["nombre"] == "Juan Alejandro Apache"
    assert response.json()["telefono"] == "3010000000"
    assert response.json()["correo"] == conductorRegistrado["correo"]
    assert response.json().keys() == PUBLIC_FIELDS
    dbSession.expire_all()
    updated = dbSession.get(Conductor, conductorId)
    assert updated.fecha_creacion == originalCreation
    assert updated.fecha_actualizacion >= originalCreation
    assert updated.password_hash == originalHash


def test_actualizacion_telefono_puede_ser_null(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any]
) -> None:
    response = client.put(
        f"/api/v1/conductores/{conductorRegistrado['conductorId']}",
        headers=authHeaders,
        json={"nombre": "Juan", "telefono": None},
    )
    assert response.status_code == 200
    assert response.json()["telefono"] is None


def test_actualizacion_omitir_telefono_lo_reemplaza_por_null(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any]
) -> None:
    response = client.put(
        f"/api/v1/conductores/{conductorRegistrado['conductorId']}",
        headers=authHeaders,
        json={"nombre": "Juan"},
    )
    assert response.status_code == 200
    assert response.json()["telefono"] is None


@pytest.mark.parametrize("conductorId", ["0", "-1", "texto", "2147483648"])
def test_identificador_path_invalido_devuelve_400(
    client: TestClient, authHeaders: dict[str, str], conductorId: str
) -> None:
    response = client.get(f"/api/v1/conductores/{conductorId}", headers=authHeaders)
    assert response.status_code == 400
    assert response.json()["detalles"]


def test_json_malformado_es_400_y_no_refleja_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/registro",
        content='{"password": "secreto-ficticio-json-roto',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "secreto-ficticio-json-roto" not in response.text


def test_openapi_contiene_solo_los_cinco_endpoints_contractuales(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    expected = {
        ("/api/v1/auth/registro", "post"),
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/me", "get"),
        ("/api/v1/conductores/{conductorId}", "get"),
        ("/api/v1/conductores/{conductorId}", "put"),
    }
    operations = {
        (path, method)
        for path, pathItem in document["paths"].items()
        for method, operation in pathItem.items()
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    }
    assert operations == expected
    for path, method in operations:
        assert "422" not in document["paths"][path][method]["responses"]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("id", 99), ("conductorId", 99), ("correo", "otro@example.com"),
        ("password", "OtraClave123!"), ("passwordHash", "hash"), ("password_hash", "hash"),
        ("activo", False), ("fechaCreacion", "2026-10-01T00:00:00Z"),
        ("fechaActualizacion", "2026-10-01T00:00:00Z"),
    ],
)
def test_actualizacion_rechaza_campos_fuera_de_contrato(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any], campo: str, valor: Any
) -> None:
    response = client.put(
        f"/api/v1/conductores/{conductorRegistrado['conductorId']}",
        headers=authHeaders,
        json={"nombre": "Juan", "telefono": None, campo: valor},
    )
    assert response.status_code == 400


def test_actualizacion_nombre_obligatorio(
    client: TestClient, authHeaders: dict[str, str], conductorRegistrado: dict[str, Any]
) -> None:
    response = client.put(
        f"/api/v1/conductores/{conductorRegistrado['conductorId']}", headers=authHeaders, json={"telefono": None}
    )
    assertError(response, 400, "CAMPO_OBLIGATORIO_FALTANTE")


def test_actualizacion_identidad_inexistente(client: TestClient, testSettings: Any) -> None:
    from app.security.jwt_service import JWTService

    response = client.put(
        "/api/v1/conductores/999999",
        headers={"Authorization": f"Bearer {JWTService(testSettings).generarToken(999999)}"},
        json={"nombre": "Juan", "telefono": None},
    )
    assertError(response, 404, "CONDUCTOR_NO_ENCONTRADO")


def test_correlation_existente_se_conserva(client: TestClient, registroPayload: dict[str, Any]) -> None:
    correlationId = str(uuid4())
    response = client.post(
        "/api/v1/auth/registro", json=registroPayload, headers={"X-Correlation-Id": correlationId}
    )
    assert response.status_code == 201
    assert response.headers["X-Correlation-Id"] == correlationId


def test_correlation_ausente_se_genera(client: TestClient, registroPayload: dict[str, Any]) -> None:
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    UUID(response.headers["X-Correlation-Id"])


def test_error_response_conserva_correlation_y_utc(client: TestClient) -> None:
    correlationId = str(uuid4())
    response = client.get("/api/v1/auth/me", headers={"X-Correlation-Id": correlationId})
    body = assertError(response, 401, "NO_AUTENTICADO")
    assert body["correlationId"] == correlationId


def test_correlation_invalida_se_rechaza(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers={"X-Correlation-Id": "no-es-uuid"})
    assertError(response, 400, "FORMATO_INVALIDO")


def test_correlation_aparece_en_logs(
    client: TestClient, registroPayload: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    correlationId = str(uuid4())
    caplog.set_level("INFO")
    logger = logging.getLogger("uniride")
    logger.addHandler(caplog.handler)
    try:
        client.post("/api/v1/auth/registro", json=registroPayload, headers={"X-Correlation-Id": correlationId})
    finally:
        logger.removeHandler(caplog.handler)
    assert correlationId in caplog.text


def test_error_500_no_expone_detalles_internos(
    client: TestClient, application: Any, registroPayload: dict[str, Any]
) -> None:
    from app.dependencies import getAuthService

    def failService() -> None:
        raise RuntimeError("SQL interno: password=secreto-ficticio-no-publicar")

    application.dependency_overrides[getAuthService] = failService
    response = client.post("/api/v1/auth/registro", json=registroPayload)
    assertError(response, 500, "ERROR_INTERNO")
    assert "SQL interno" not in response.text
    assert "secreto-ficticio-no-publicar" not in response.text


def test_timestamps_de_persistencia_utc(
    conductorRegistrado: dict[str, Any], dbSession: Session
) -> None:
    from app.models.conductor import Conductor

    conductor = dbSession.get(Conductor, conductorRegistrado["conductorId"])
    # SQL Server DATETIME2 no almacena zona: la aplicación siempre escribe UTC.
    nowUtc = datetime.now(timezone.utc).replace(tzinfo=None)
    assert conductor.fecha_creacion.tzinfo is None
    assert abs((nowUtc - conductor.fecha_creacion).total_seconds()) < 60
    assert conductor.fecha_actualizacion >= conductor.fecha_creacion
