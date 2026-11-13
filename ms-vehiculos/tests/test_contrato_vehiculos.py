import os
import time

import jwt

from tests.conftest import VEHICULO, cabeceras, tokenDe

RUTA = "/api/v1/vehiculos"


def test_sin_token_responde_401_con_formato_unico(cliente):
    r = cliente.get(RUTA)
    assert r.status_code == 401
    cuerpo = r.json()
    assert cuerpo["error"] == "NO_AUTENTICADO"
    assert set(cuerpo) >= {"timestamp", "status", "error", "message", "path", "correlationId"}
    assert r.headers["X-Correlation-Id"] == cuerpo["correlationId"]


def test_token_vencido_responde_401(cliente):
    ahora = int(time.time())
    vencido = jwt.encode(
        {"sub": "1", "iat": ahora - 7200, "exp": ahora - 3600},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )
    r = cliente.get(RUTA, headers={"Authorization": f"Bearer {vencido}"})
    assert r.status_code == 401


def test_registrar_devuelve_201_camelcase_y_estado_activo(cliente):
    r = cliente.post(RUTA, json=VEHICULO, headers=cabeceras(7))
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo == {
        "vehiculoId": 1, "conductorId": 7, "placa": "ABC123", "marca": "Renault",
        "modelo": "Logan", "color": "Gris", "tipo": "Automovil",
        "capacidad": 4, "estado": "ACTIVO",
    }


def test_conductor_id_del_body_debe_coincidir_con_el_token(cliente):
    r = cliente.post(RUTA, json={**VEHICULO, "conductorId": 8}, headers=cabeceras(7))
    assert r.status_code == 403
    assert r.json()["error"] == "NO_AUTORIZADO"
    r = cliente.post(RUTA, json={**VEHICULO, "conductorId": 7}, headers=cabeceras(7))
    assert r.status_code == 201


def test_placa_duplicada_responde_409(cliente):
    cliente.post(RUTA, json=VEHICULO, headers=cabeceras(7))
    r = cliente.post(RUTA, json=VEHICULO, headers=cabeceras(8))
    assert r.status_code == 409
    assert r.json()["error"] == "PLACA_YA_REGISTRADA"


def test_listado_solo_trae_los_del_conductor_dentro_de_datos(cliente):
    cliente.post(RUTA, json=VEHICULO, headers=cabeceras(7))
    cliente.post(RUTA, json={**VEHICULO, "placa": "XYZ789"}, headers=cabeceras(8))
    r = cliente.get(RUTA, headers=cabeceras(7))
    assert r.status_code == 200
    datos = r.json()["datos"]
    assert [v["placa"] for v in datos] == ["ABC123"]


def test_consultar_ajeno_403_e_inexistente_404(cliente):
    cliente.post(RUTA, json=VEHICULO, headers=cabeceras(7))
    assert cliente.get(f"{RUTA}/1", headers=cabeceras(8)).status_code == 403
    r = cliente.get(f"{RUTA}/99", headers=cabeceras(7))
    assert r.status_code == 404
    assert r.json()["error"] == "VEHICULO_NO_ENCONTRADO"
    assert cliente.get(f"{RUTA}/1", headers=cabeceras(7)).status_code == 200


def test_modificar_propio_200_y_ajeno_403(cliente):
    cliente.post(RUTA, json=VEHICULO, headers=cabeceras(7))
    nuevo = {**VEHICULO, "color": "Rojo", "capacidad": 5}
    r = cliente.put(f"{RUTA}/1", json=nuevo, headers=cabeceras(7))
    assert r.status_code == 200
    assert r.json()["color"] == "Rojo" and r.json()["capacidad"] == 5
    assert cliente.put(f"{RUTA}/1", json=nuevo, headers=cabeceras(8)).status_code == 403


def test_baja_es_logica_204_y_queda_inactivo(cliente):
    cliente.post(RUTA, json=VEHICULO, headers=cabeceras(7))
    r = cliente.delete(f"{RUTA}/1", headers=cabeceras(7))
    assert r.status_code == 204 and r.content == b""
    assert cliente.get(f"{RUTA}/1", headers=cabeceras(7)).json()["estado"] == "INACTIVO"
    assert cliente.delete(f"{RUTA}/1", headers=cabeceras(8)).status_code == 403


def test_capacidad_invalida_400_con_detalles(cliente):
    r = cliente.post(RUTA, json={**VEHICULO, "capacidad": 0}, headers=cabeceras(7))
    assert r.status_code == 400
    cuerpo = r.json()
    assert cuerpo["error"] == "CAPACIDAD_INVALIDA"
    assert cuerpo["detalles"][0]["campo"] == "capacidad"


def test_campo_faltante_y_campo_extra_400(cliente):
    sinMarca = {k: v for k, v in VEHICULO.items() if k != "marca"}
    r = cliente.post(RUTA, json=sinMarca, headers=cabeceras(7))
    assert r.status_code == 400 and r.json()["error"] == "CAMPO_OBLIGATORIO_FALTANTE"
    r = cliente.post(RUTA, json={**VEHICULO, "estado": "INACTIVO"}, headers=cabeceras(7))
    assert r.status_code == 400


def test_id_de_ruta_no_positivo_400(cliente):
    assert cliente.get(f"{RUTA}/0", headers=cabeceras(7)).status_code == 400
    assert cliente.get(f"{RUTA}/abc", headers=cabeceras(7)).status_code == 400


def test_correlation_id_recibido_se_devuelve(cliente):
    cid = "5b9c2e7d-1171-4b93-a2aa-91af32d6b709"
    r = cliente.get(RUTA, headers={**cabeceras(7), "X-Correlation-Id": cid})
    assert r.headers["X-Correlation-Id"] == cid
    r = cliente.get(f"{RUTA}/99", headers={**cabeceras(7), "X-Correlation-Id": cid})
    assert r.json()["correlationId"] == cid
