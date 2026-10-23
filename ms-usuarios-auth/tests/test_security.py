"""Contrato de JWT HS256 y hash de contraseñas independiente de SQL Server."""

from datetime import datetime, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_JWT_SECRET, TEST_PASSWORD
from tests.test_api import assertError


def tokenConClaims(claims: dict[str, Any], secret: str = TEST_JWT_SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(claims, secret, algorithm=algorithm)


def validClaims() -> dict[str, Any]:
    now = int(datetime.now(timezone.utc).timestamp())
    return {"sub": "1", "iat": now, "exp": now + 3600}


def test_jwt_claims_exactos_y_sub_texto(autenticacion: dict[str, Any]) -> None:
    claims = jwt.decode(autenticacion["accessToken"], TEST_JWT_SECRET, algorithms=["HS256"])
    assert claims.keys() == {"sub", "iat", "exp"}
    assert claims["sub"] == str(autenticacion["conductorId"])
    assert isinstance(claims["sub"], str)
    assert isinstance(claims["iat"], int)
    assert isinstance(claims["exp"], int)


def test_jwt_algoritmo_hs256(autenticacion: dict[str, Any]) -> None:
    assert jwt.get_unverified_header(autenticacion["accessToken"])["alg"] == "HS256"


def test_jwt_ttl_configurable(testSettings: Any) -> None:
    from app.security.jwt_service import JWTService

    settings = testSettings.model_copy(update={"JWT_EXPIRES_IN_SECONDS": 120})
    token = JWTService(settings).generarToken(25)
    claims = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 120
    assert JWTService(settings).validarToken(token) == 25


def test_jwt_ttl_por_defecto(autenticacion: dict[str, Any]) -> None:
    claims = jwt.decode(autenticacion["accessToken"], TEST_JWT_SECRET, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 3600


@pytest.mark.parametrize("authorization", [None, "", "Basic abc", "Bearer", "Bearer a b", "Bearer no-es-un-jwt"])
def test_jwt_ausente_o_bearer_invalido(client: TestClient, authorization: str | None) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.get("/api/v1/auth/me", headers=headers)
    assertError(response, 401, "NO_AUTENTICADO")


def test_jwt_firma_invalida(client: TestClient) -> None:
    token = tokenConClaims(validClaims(), secret="otra-clave-ficticia-pruebas-1234567890")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assertError(response, 401, "NO_AUTENTICADO")


def test_jwt_algoritmo_no_autorizado(client: TestClient) -> None:
    token = tokenConClaims(validClaims(), algorithm="HS384")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assertError(response, 401, "NO_AUTENTICADO")


def test_jwt_vencido(client: TestClient) -> None:
    claims = validClaims()
    claims["iat"] -= 7200
    claims["exp"] -= 7200
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokenConClaims(claims)}"})
    assertError(response, 401, "NO_AUTENTICADO")


@pytest.mark.parametrize(
    ("claim", "valor"),
    [("iat", "no-numero"), ("iat", True), ("iat", 1.5), ("exp", "no-numero"), ("exp", True), ("exp", 1.5)],
)
def test_jwt_timestamps_requieren_enteros(client: TestClient, claim: str, valor: Any) -> None:
    claims = validClaims()
    claims[claim] = valor
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokenConClaims(claims)}"})
    assertError(response, 401, "NO_AUTENTICADO")


def test_jwt_iat_futuro_es_invalido(client: TestClient) -> None:
    claims = validClaims()
    claims["iat"] += 300
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokenConClaims(claims)}"})
    assertError(response, 401, "NO_AUTENTICADO")


@pytest.mark.parametrize("claim", ["sub", "iat", "exp"])
def test_jwt_requiere_claims(client: TestClient, claim: str) -> None:
    claims = validClaims()
    claims.pop(claim)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokenConClaims(claims)}"})
    assertError(response, 401, "NO_AUTENTICADO")


@pytest.mark.parametrize("subject", [1, "abc", "0", "-1", "1.2", " 1", "+1", "2147483648", "١"])
def test_jwt_sub_requiere_entero_positivo_en_texto(client: TestClient, subject: Any) -> None:
    claims = validClaims()
    claims["sub"] = subject
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokenConClaims(claims)}"})
    assertError(response, 401, "NO_AUTENTICADO")


def test_hash_argon2id_verifica_password() -> None:
    from app.security.password_service import PasswordService

    service = PasswordService()
    passwordHash = service.hashPassword(TEST_PASSWORD)
    assert passwordHash.startswith("$argon2id$")
    assert service.verifyPassword(TEST_PASSWORD, passwordHash)
    assert not service.verifyPassword("ClaveDistinta123!", passwordHash)


def test_hash_utiliza_salt_aleatoria() -> None:
    from app.security.password_service import PasswordService

    service = PasswordService()
    assert service.hashPassword(TEST_PASSWORD) != service.hashPassword(TEST_PASSWORD)


def test_password_larga_no_se_trunca_a_72_bytes() -> None:
    from app.security.password_service import PasswordService

    service = PasswordService()
    password = "á" * 80 + "A"
    passwordHash = service.hashPassword(password)
    assert service.verifyPassword(password, passwordHash)
    assert not service.verifyPassword("á" * 80 + "B", passwordHash)


def test_hash_corrupto_no_autentica() -> None:
    from app.security.password_service import PasswordService

    assert not PasswordService().verifyPassword(TEST_PASSWORD, "hash-corrupto-ficticio")
