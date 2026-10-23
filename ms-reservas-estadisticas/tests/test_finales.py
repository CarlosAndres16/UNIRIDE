"""Aceptacion HTTP de los cinco endpoints y sus dependencias en memoria."""

from datetime import UTC, datetime
import json
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.reserva import Reserva, EstadoReserva
from app.services.estadistica_service import _porcentaje
from tests.apoyo import sistema
from tests.contrato import RUTAS_CONTRATO

RUTAS = (
    "/api/v1/reservas/viaje/305", "/api/v1/reservas/1",
    "/api/v1/estadisticas/viaje/305", "/api/v1/estadisticas/conductor/25",
    "/api/v1/estadisticas/vehiculo/12",
)


@pytest.fixture
def local():
    with patch("app.config.database.getSessionFactory", side_effect=AssertionError("SQL real prohibido en suite aislada")):
        with sistema() as instancia:
            yield instancia


def consultar(local, ruta, **kwargs):
    return local.client.get(ruta, headers=local.headers(), **kwargs)


def error(response, status, codigo=None):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"timestamp", "status", "error", "message", "path", "correlationId"} | ({"detalles"} if status == 400 else set())
    assert body["status"] == status
    assert body["path"] == response.request.url.path
    assert body["correlationId"] == response.headers["X-Correlation-Id"]
    UUID(body["correlationId"])
    assert body["timestamp"].endswith("Z")
    if codigo:
        assert body["error"] == codigo
    return body


def agregar(local, *, viajeId=305, cupos=1, estado=EstadoReserva.CONFIRMADA):
    local.repository.datos.append(Reserva(
        id=max(r.id for r in local.repository.datos) + 1,
        viajeId=viajeId, pasajeroNombre="Pasajero de prueba", cuposReservados=cupos,
        estado=estado, fechaReserva=datetime(2026, 10, 1, tzinfo=UTC),
    ))


def puts(local):
    return [r for r in local.transporte.requests if r.method == "PUT"]


def test_swagger_contrato_exacto_y_sin_escrituras(local):
    respuesta = local.client.get("/openapi.json")
    assert respuesta.status_code == 200
    paths = respuesta.json()["paths"]
    assert set(paths) == RUTAS_CONTRATO
    for operacion in paths.values():
        assert set(operacion) == {"get"}
        assert operacion["get"]["security"] == [{"BearerAuth": []}]
        assert "422" not in operacion["get"]["responses"]
    assert local.client.get("/docs").status_code == 200


@pytest.mark.parametrize("ruta", RUTAS)
def test_cinco_consultas_validas_con_clientes_reales(local, ruta):
    respuesta = consultar(local, ruta)
    assert respuesta.status_code == 200
    UUID(respuesta.headers["X-Correlation-Id"])


@pytest.mark.parametrize("ruta", RUTAS)
@pytest.mark.parametrize("modo", ("ausente", "invalido", "vencido", "otra_firma"))
def test_jwt_invalido_bloquea_antes_de_dependencias(local, ruta, modo):
    error(local.client.get(ruta, headers=local.headers(modo=modo)), 401, "NO_AUTENTICADO")
    assert local.eventos == []
    assert local.transporte.requests == []


@pytest.mark.parametrize("ruta", RUTAS)
def test_dueno_ajeno_no_recibe_datos(local, ruta):
    respuesta = local.client.get(ruta, headers=local.headers(26))
    error(respuesta, 403, "NO_AUTORIZADO")
    assert "Laura" not in respuesta.text
    assert "resumen" not in local.eventos
    if ruta != "/api/v1/reservas/1":
        assert local.eventos == []


@pytest.mark.parametrize("ruta", RUTAS)
@pytest.mark.parametrize("metodo", ("POST", "PUT", "PATCH", "DELETE"))
def test_api_de_lectura_no_admite_mutaciones(local, ruta, metodo):
    assert local.client.request(metodo, ruta, headers=local.headers()).status_code == 405
    assert local.eventos == []
    assert local.transporte.requests == []


@pytest.mark.parametrize("ruta,codigo", (
    ("/api/v1/reservas/999999", "RESERVA_NO_ENCONTRADA"),
    ("/api/v1/reservas/viaje/999999", "VIAJE_NO_ENCONTRADO"),
    ("/api/v1/estadisticas/viaje/999999", "VIAJE_NO_ENCONTRADO"),
    ("/api/v1/estadisticas/vehiculo/999999", "VEHICULO_NO_ENCONTRADO"),
))
def test_recurso_inexistente_404(local, ruta, codigo):
    error(consultar(local, ruta), 404, codigo)
    assert not puts(local)


def test_detalle_devuelve_dto_completo_y_autoriza_antes_del_resumen(local):
    body = consultar(local, RUTAS[1]).json()
    assert body == {
        "reservaId": 1, "viajeId": 305, "pasajeroNombre": "Laura Gómez",
        "cuposReservados": 1, "estado": "CONFIRMADA", "fechaReserva": "2026-10-01T14:20:00Z",
    }
    assert local.eventos == ["detalle", "resumen"]
    assert local.transporte.requests[0].url.path == "/api/v1/viajes/305"


def test_estadistica_viaje_valores_y_campos_exactos(local):
    assert consultar(local, RUTAS[2]).json() == {
        "viajeId": 305, "vehiculoId": 12, "cuposOfrecidos": 4,
        "totalReservas": 3, "reservasConfirmadas": 2, "reservasCanceladas": 1,
        "reservasPendientes": 0, "pasajerosConfirmados": 2,
        "cuposDisponibles": 2, "porcentajeOcupacion": 50.0,
    }
    assert not puts(local)


def test_conductor_cancela_excluidos_y_promedio_ponderado(local):
    agregar(local, viajeId=307, cupos=100)
    assert consultar(local, RUTAS[3]).json() == {
        "conductorId": 25, "periodo": None, "viajesConsultados": 3,
        "vehiculosUtilizados": 2, "totalReservas": 3, "reservasConfirmadas": 2,
        "reservasCanceladas": 1, "pasajerosConfirmados": 2, "porcentajeOcupacionPromedio": 20.0,
    }


def test_vehiculo_usa_solo_sus_viajes_y_capacidades_historicas(local):
    agregar(local, viajeId=308)
    vehiculo = local.vehiculos.state.vehiculos[12]
    local.vehiculos.state.vehiculos[12] = vehiculo.model_copy(update={"capacidad": 8})
    assert consultar(local, RUTAS[4]).json() == {
        "vehiculoId": 12, "conductorId": 25, "periodo": None,
        "viajesConsultados": 2, "totalReservas": 3, "reservasConfirmadas": 2,
        "reservasCanceladas": 1, "pasajerosConfirmados": 2,
        "cuposOfrecidosAcumulados": 8, "porcentajeOcupacionPromedio": 25.0,
    }


@pytest.mark.parametrize("parametros,viajes,porcentaje", (
    ({"desde": "2026-10-25", "hasta": "2026-10-25"}, 1, 50.0),
    ({"desde": "2026-10-26"}, 1, 0.0),
    ({"hasta": "2026-10-01"}, 1, 0.0),
    ({"desde": "2026-11-01", "hasta": "2026-11-30"}, 0, 0.0),
))
def test_fechas_inclusivas_periodos_parciales_y_cero(local, parametros, viajes, porcentaje):
    respuesta = consultar(local, RUTAS[3], params=parametros)
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["periodo"] == {"desde": parametros.get("desde"), "hasta": parametros.get("hasta")}
    assert body["viajesConsultados"] == viajes
    assert body["porcentajeOcupacionPromedio"] == porcentaje


@pytest.mark.parametrize("ruta", RUTAS[3:])
@pytest.mark.parametrize("params", (
    {"desde": "2026-10-31", "hasta": "2026-10-01"},
    {"desde": "2026-02-30"}, {"desde": "2026-10-01T00:00:00Z"}, {"hasta": "1790000000"},
))
def test_fechas_invalidas_400_antes_http_sql(local, ruta, params):
    error(consultar(local, ruta, params=params), 400)
    assert local.transporte.requests == []
    assert local.eventos == []


def test_vehiculo_inactivo_sin_viajes_devuelve_ceros_sin_sql(local):
    respuesta = consultar(local, "/api/v1/estadisticas/vehiculo/15")
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["viajesConsultados"] == body["totalReservas"] == body["pasajerosConfirmados"] == 0
    assert body["porcentajeOcupacionPromedio"] == 0.0
    assert local.eventos == []


def test_multiples_paginas_incluye_reserva_de_segunda_pagina(local):
    agregar(local, viajeId=1050, cupos=3)
    respuesta = local.client.get("/api/v1/estadisticas/conductor/27", headers=local.headers(27))
    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["viajesConsultados"] == 51
    assert body["pasajerosConfirmados"] == 3
    assert body["porcentajeOcupacionPromedio"] == 1.47
    paginas = [r for r in local.transporte.requests if r.url.path == "/api/v1/viajes"]
    assert [r.url.params["pagina"] for r in paginas] == ["1", "2"]
    assert all(r.url.params["tamano"] == "50" and r.url.params["estado"] == "TODOS" for r in paginas)


def test_sumar_cupos_no_confundir_con_numero_de_reservas(local):
    local.repository.datos[0].cuposReservados = 2
    agregar(local, cupos=7, estado=EstadoReserva.PENDIENTE)
    body = consultar(local, RUTAS[2]).json()
    assert (body["totalReservas"], body["reservasConfirmadas"], body["reservasPendientes"]) == (4, 2, 1)
    assert (body["pasajerosConfirmados"], body["cuposDisponibles"], body["porcentajeOcupacion"]) == (3, 1, 75.0)
    assert json.loads(puts(local)[0].content) == {"cuposOcupados": 3}


@pytest.mark.parametrize("estado", ("PENDIENTE", "CONFIRMADA", "CANCELADA"))
def test_filtro_estado_no_recorta_total_informado(local, estado):
    local.repository.datos[0].cuposReservados = 2
    respuesta = consultar(local, RUTAS[0], params={"estado": estado})
    assert respuesta.status_code == 200
    assert all(r["estado"] == estado for r in respuesta.json()["datos"])
    assert json.loads(puts(local)[0].content) == {"cuposOcupados": 3}


def test_correlacion_jwt_get_y_llave_put_sin_mezclarlos(local):
    local.repository.datos[0].cuposReservados = 2
    correlationId = str(uuid4())
    headers = local.headers(correlationId=correlationId)
    respuesta = local.client.get(RUTAS[2], headers=headers)
    assert respuesta.status_code == 200
    assert respuesta.headers["X-Correlation-Id"] == correlationId
    get, put = local.transporte.requests
    assert get.headers["Authorization"] == headers["Authorization"]
    assert "X-Service-Key" not in get.headers
    assert "Authorization" not in put.headers
    assert put.headers["X-Service-Key"] == local.llave.get_secret_value()
    assert all(r.headers["X-Correlation-Id"] == correlationId for r in (get, put))


def test_ocupacion_idempotente_no_repite_put_si_ya_coincide(local):
    local.repository.datos[0].cuposReservados = 2
    assert consultar(local, RUTAS[2]).status_code == 200
    version = local.viajes.state.viajes[305].version
    assert consultar(local, RUTAS[2]).status_code == 200
    assert len(puts(local)) == 1
    assert local.viajes.state.viajes[305].version == version


@pytest.mark.parametrize("fallo", ("caido", "timeout", "invalido"))
def test_fallo_put_no_rompe_lectura_reintenta_y_recupera(local, fallo):
    local.repository.datos[0].cuposReservados = 2
    local.transporte.fallos[("viajes.test", "PUT")] = fallo
    respuesta = consultar(local, RUTAS[2])
    assert respuesta.status_code == 200
    assert respuesta.json()["pasajerosConfirmados"] == 3
    assert len(puts(local)) == 2
    local.transporte.fallos.clear()
    assert consultar(local, RUTAS[2]).status_code == 200
    assert len(puts(local)) == 3
    assert local.viajes.state.viajes[305].cuposDisponibles == 1


def test_llave_interna_rechazada_no_rompe_consulta(local):
    from pydantic import SecretStr
    from mocks.common import getServiceApiKey
    local.viajes.dependency_overrides[getServiceApiKey] = lambda: SecretStr("otra-llave-solo-prueba")
    local.repository.datos[0].cuposReservados = 2
    assert consultar(local, RUTAS[2]).status_code == 200
    assert len(puts(local)) == 1


@pytest.mark.parametrize("viajeId", (306, 307))
def test_finalizado_cancelado_no_reciben_put(local, viajeId):
    agregar(local, viajeId=viajeId)
    assert consultar(local, f"/api/v1/estadisticas/viaje/{viajeId}").status_code == 200
    assert not puts(local)


def test_sobrecapacidad_conserva_total_y_disponibilidad_no_negativa(local):
    agregar(local, cupos=10)
    body = consultar(local, RUTAS[2]).json()
    assert (body["pasajerosConfirmados"], body["cuposDisponibles"], body["porcentajeOcupacion"]) == (12, 0, 100.0)
    assert json.loads(puts(local)[0].content) == {"cuposOcupados": 12}
    assert len(puts(local)) == 1


@pytest.mark.parametrize("ruta,host", ((RUTAS[2], "viajes.test"), (RUTAS[4], "vehiculos.test")))
@pytest.mark.parametrize("fallo", ("caido", "timeout", "invalido"))
def test_dependencia_fallida_503_dos_intentos_sin_sql(local, ruta, host, fallo):
    local.transporte.fallos[(host, "GET")] = fallo
    error(consultar(local, ruta), 503, "SERVICIO_DEPENDIENTE_NO_DISPONIBLE")
    assert len(local.transporte.requests) == 2
    assert local.eventos == []


def test_error_sql_no_expone_detalles_ni_credenciales(local, caplog):
    privado = "CONTENIDO_SQL_PRIVADO"
    local.repository.fallo = SQLAlchemyError(privado)
    respuesta = consultar(local, RUTAS[2])
    error(respuesta, 500, "ERROR_INTERNO")
    assert privado not in respuesta.text
    assert not puts(local)


@pytest.mark.parametrize("pasajeros,capacidad,esperado", ((2, 0, 0.0), (1, 3, 33.33), (2, 3, 66.67), (5, 4, 100.0)))
def test_porcentaje_redondeo_cero_y_limite(pasajeros, capacidad, esperado):
    assert _porcentaje(pasajeros, capacidad, str(uuid4())) == esperado


def test_postman_sin_secretos_y_con_las_cinco_consultas():
    raiz = Path(__file__).resolve().parents[1] / "postman"
    collection = json.loads((raiz / "UniRide-Reservas-Estadisticas.postman_collection.json").read_text(encoding="utf-8"))
    environment = json.loads((raiz / "UniRide-Local.postman_environment.json").read_text(encoding="utf-8"))
    variables = {v["key"]: v["value"] for v in environment["values"]}
    assert variables["accessToken"] == variables["serviceApiKey"] == ""
    solicitudes = [r["request"] for folder in collection["item"][:2] for r in folder["item"]]
    assert len(solicitudes) == 5
    assert all(r["method"] == "GET" and r["url"]["raw"].startswith("{{baseUrl}}/api/v1/") for r in solicitudes)
