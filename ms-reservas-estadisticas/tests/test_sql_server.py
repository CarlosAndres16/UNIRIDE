"""Lecturas reales optativas: no seed, DDL, INSERT, UPDATE ni DELETE."""

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import getEngine
from app.repositories.reserva_repository import ReservaRepository
from tests.apoyo import sistema

pytestmark = pytest.mark.sql_server


@pytest.fixture(scope="module")
def motor():
    try:
        engine = getEngine()
        with engine.connect() as connection:
            nombre = connection.execute(text("SELECT DB_NAME()" )).scalar_one()
    except (SQLAlchemyError, ValidationError):
        pytest.fail("No se pudo conectar a SQL Server. Revisar configuracion privada y servicio SQL.", pytrace=False)
    assert nombre == "unirride_reservas", "Las pruebas solo permiten la base propia."
    try:
        yield engine
    finally:
        engine.dispose()


def test_base_propia_migracion_y_tablas(motor):
    tablas = set(inspect(motor).get_table_names(schema="dbo"))
    assert {"reservas", "alembic_version"}.issubset(tablas)
    assert not any("estadistica" in tabla.lower() for tabla in tablas)
    with motor.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar_one() == "0001_crear_reservas"


def test_repositorio_y_cupos_coinciden_con_sql_real(motor):
    with Session(motor) as session:
        repository = ReservaRepository(session)
        filas = repository.listarPorViaje(305)
        assert filas, "Se requiere el seed del viaje 305, sin crearlo desde las pruebas."
        resumen = repository.resumirPorViajes([305])[305]
        sql = session.execute(text("""
            SELECT COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN estado = 'CONFIRMADA' THEN 1 ELSE 0 END), 0) AS confirmadas,
                COALESCE(SUM(CASE WHEN estado = 'CONFIRMADA' THEN CAST(cupos_reservados AS BIGINT) ELSE 0 END), 0) AS pasajeros
            FROM dbo.reservas WHERE viaje_id = :viajeId
        """), {"viajeId": 305}).mappings().one()
        assert (resumen.totalReservas, resumen.reservasConfirmadas, resumen.pasajerosConfirmados) == (sql["total"], sql["confirmadas"], sql["pasajeros"])
        assert all(r.fechaReserva.utcoffset().total_seconds() == 0 for r in filas)


def test_api_cinco_endpoints_con_sql_real_y_dependencias_simuladas(motor):
    with Session(motor) as session:
        repository = ReservaRepository(session)
        reservas = repository.listarPorViaje(305)
        assert reservas, "Se requiere el seed del viaje 305."
        resumen = repository.resumirPorViajes([305])[305]
        with sistema(repository) as local:
            rutas = (
                "/api/v1/reservas/viaje/305", f"/api/v1/reservas/{reservas[0].id}",
                "/api/v1/estadisticas/viaje/305", "/api/v1/estadisticas/conductor/25",
                "/api/v1/estadisticas/vehiculo/12",
            )
            respuestas = [local.client.get(r, headers=local.headers()) for r in rutas]
            assert [r.status_code for r in respuestas] == [200] * 5
            assert respuestas[0].json()["total"] == resumen.totalReservas
            assert respuestas[1].json()["reservaId"] == reservas[0].id
            assert respuestas[2].json()["pasajerosConfirmados"] == resumen.pasajerosConfirmados
            assert respuestas[2].json()["porcentajeOcupacion"] == min(100.0, round(resumen.pasajerosConfirmados / 4 * 100, 2))
            assert respuestas[3].json()["viajesConsultados"] == 3
            assert respuestas[4].json()["viajesConsultados"] == 2
