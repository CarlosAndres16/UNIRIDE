import pytest
from scripts.seed_reservas import cargarReservas, DATOS_PRUEBA


class SesionEjemplo:
    def __init__(self):
        self.calls = 0
        self.added = []
    def scalar(self, statement):
        self.calls += 1
        return 'unirride_reservas' if self.calls == 1 else None
    def add(self, reserva):
        self.added.append(reserva)


def test_seed_usa_id_real_sin_mutar_ejemplos():
    session = SesionEjemplo()
    assert cargarReservas(session, 72) == (3, 0)
    assert [r.viajeId for r in session.added] == [72, 72, 72]
    assert all(r['viajeId'] == 305 for r in DATOS_PRUEBA)


@pytest.mark.parametrize('invalid', [0, -1, True, '72', 2147483648])
def test_seed_rechaza_id_invalido_antes_de_sql(invalid):
    session = SesionEjemplo()
    with pytest.raises(ValueError):
        cargarReservas(session, invalid)
    assert session.calls == 0
