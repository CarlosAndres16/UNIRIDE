"""Contrato SQL Server del agregado, incluyendo bloques y datos invalidos."""

import pytest
from sqlalchemy.dialects import mssql

from app.repositories.reserva_repository import ReservaRepository, ResumenReservas


class SesionLectura:
    def __init__(self, filas=()):
        self.filas = filas
        self.consultas = []

    def execute(self, consulta):
        assert consulta.is_select
        assert [t.fullname for t in consulta.get_final_froms()] == ["dbo.reservas"]
        self.consultas.append(consulta)
        ids = next(iter(consulta.compile(dialect=mssql.dialect()).params.values()))
        filas = [fila for fila in self.filas if fila[0] in ids]
        return type("Filas", (), {"all": lambda self: filas})()


def test_agregado_suma_cupos_y_distingue_estados():
    sesion = SesionLectura(((305, "CONFIRMADA", 2, 5), (305, "CANCELADA", 1, 3), (305, "PENDIENTE", 1, 2)))
    resumen = ReservaRepository(sesion).resumirPorViajes([305, 308])
    assert resumen == {305: ResumenReservas(4, 2, 1, 1, 5), 308: ResumenReservas()}
    sql = str(sesion.consultas[0].compile(dialect=mssql.dialect())).upper()
    assert "BIGINT" in sql and "GROUP BY" in sql
    assert "305" not in sql


def test_mas_de_dos_mil_ids_en_bloques_sin_duplicados():
    sesion = SesionLectura(((1, "CONFIRMADA", 1, 2), (2001, "CONFIRMADA", 1, 3)))
    ids = list(range(1, 2502)) + [1, 2001]
    resumenes = ReservaRepository(sesion).resumirPorViajes(ids)
    bloques = [next(iter(c.compile(dialect=mssql.dialect()).params.values())) for c in sesion.consultas]
    assert [len(b) for b in bloques] == [1000, 1000, 501]
    assert len(resumenes) == 2501
    assert sum(r.pasajerosConfirmados for r in resumenes.values()) == 5


def test_sin_ids_no_ejecuta_sql():
    sesion = SesionLectura()
    assert ReservaRepository(sesion).resumirPorViajes([]) == {}
    assert sesion.consultas == []


@pytest.mark.parametrize("fila", ((305, "DESCONOCIDO", 1, 1), (305, "CONFIRMADA", 2, 1), (305, "CONFIRMADA", 0, 0)))
def test_agregado_corrupto_no_desaparece_silenciosamente(fila):
    with pytest.raises(ValueError):
        ReservaRepository(SesionLectura((fila,))).resumirPorViajes([305])


@pytest.mark.parametrize("ids", ([0], [-1], [True], ["305"]))
def test_identificadores_invalidos_no_alcanzan_sql(ids):
    sesion = SesionLectura()
    with pytest.raises(ValueError):
        ReservaRepository(sesion).resumirPorViajes(ids)
    assert sesion.consultas == []
