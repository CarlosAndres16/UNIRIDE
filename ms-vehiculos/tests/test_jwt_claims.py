import os
import time

import jwt
import pytest


@pytest.mark.parametrize(
    "cambios",
    [
        {"iat": "ayer"},
        {"iat": True},
        {"iat": 1.5},
        {"iat": "1"},
        {"iat": int(time.time()) + 3600},
        {"exp": str(int(time.time()) + 3600)},
        {"exp": float(int(time.time()) + 3600)},
        {"iat": int(time.time()) + 7200, "exp": int(time.time()) + 3600},
        {"sub": 7},
        {"sub": "0"},
        {"sub": "2147483648"},
    ],
)
def test_claims_invalidos_se_rechazan_con_401(cliente, cambios):
    ahora = int(time.time())
    claims = {"sub": "7", "iat": ahora, "exp": ahora + 3600, **cambios}
    token = jwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")
    response = cliente.get("/api/v1/vehiculos", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["error"] == "NO_AUTENTICADO"
