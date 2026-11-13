"""Acceso a la base unirride_vehiculos. Traduce los errores del driver al contrato."""

from psycopg import InterfaceError, OperationalError
from psycopg.errors import UniqueViolation

from app.config.database import abrirConexion
from app.config.settings import Settings
from app.exceptions.exceptions import AppException

COLUMNAS = "id, conductor_id, placa, marca, modelo, color, tipo, capacidad, estado"


class VehiculoRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _ejecutar(self, operacion):
        try:
            with abrirConexion(self._settings) as conexion:
                with conexion.cursor() as cursor:
                    return operacion(cursor)
        except UniqueViolation:
            raise AppException(
                409, "PLACA_YA_REGISTRADA", "Ya existe un vehículo registrado con esa placa."
            ) from None
        except (OperationalError, InterfaceError):
            raise AppException(
                503,
                "SERVICIO_DEPENDIENTE_NO_DISPONIBLE",
                "La base de datos no está disponible. Intente de nuevo más tarde.",
            ) from None

    def crear(self, conductorId: int, datos: dict) -> dict:
        def operacion(cursor):
            cursor.execute(
                f"""
                INSERT INTO vehiculos
                    (conductor_id, placa, marca, modelo, color, tipo, capacidad, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                RETURNING {COLUMNAS}
                """,
                (conductorId, datos["placa"], datos["marca"], datos["modelo"],
                 datos["color"], datos["tipo"], datos["capacidad"]),
            )
            return cursor.fetchone()

        return self._ejecutar(operacion)

    def listarPorConductor(self, conductorId: int) -> list[dict]:
        def operacion(cursor):
            cursor.execute(
                f"SELECT {COLUMNAS} FROM vehiculos WHERE conductor_id = %s ORDER BY id",
                (conductorId,),
            )
            return cursor.fetchall()

        return self._ejecutar(operacion)

    def obtener(self, vehiculoId: int) -> dict | None:
        def operacion(cursor):
            cursor.execute(
                f"SELECT {COLUMNAS} FROM vehiculos WHERE id = %s", (vehiculoId,)
            )
            return cursor.fetchone()

        return self._ejecutar(operacion)

    def actualizar(self, vehiculoId: int, datos: dict) -> dict | None:
        def operacion(cursor):
            cursor.execute(
                f"""
                UPDATE vehiculos
                   SET placa = %s, marca = %s, modelo = %s, color = %s,
                       tipo = %s, capacidad = %s, fecha_actualizacion = now()
                 WHERE id = %s
                RETURNING {COLUMNAS}
                """,
                (datos["placa"], datos["marca"], datos["modelo"], datos["color"],
                 datos["tipo"], datos["capacidad"], vehiculoId),
            )
            return cursor.fetchone()

        return self._ejecutar(operacion)

    def darDeBaja(self, vehiculoId: int) -> None:
        """Baja lógica (D-15): el estado pasa a INACTIVO, la fila se conserva."""

        def operacion(cursor):
            cursor.execute(
                "UPDATE vehiculos SET estado = 'INACTIVO', fecha_actualizacion = now() "
                "WHERE id = %s",
                (vehiculoId,),
            )

        self._ejecutar(operacion)
