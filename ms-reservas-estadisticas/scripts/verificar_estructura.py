"""Inspecciona la estructura migrada sin insertar, modificar ni borrar reservas."""

import sys

from alembic.runtime.migration import MigrationContext
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Integer, func, inspect, select, text
from sqlalchemy.dialects.mssql import DATETIME2, NVARCHAR
from sqlalchemy.exc import SQLAlchemyError

from app.config.database import getEngine
from app.models import Reserva


def exigir(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    engine = None
    try:
        engine = getEngine()
        with engine.connect() as connection:
            inspector = inspect(connection)
            exigir(inspector.has_table("reservas", schema="dbo"), "Falta dbo.reservas.")
            columns = {
                column["name"]: column
                for column in inspector.get_columns("reservas", schema="dbo")
            }
            exigir(
                set(columns) == set(Reserva.__table__.columns.keys()),
                "Las columnas no coinciden con las seis columnas del contrato.",
            )
            exigir(
                all(not column["nullable"] for column in columns.values()),
                "Todas las columnas deben ser NOT NULL.",
            )
            for name in ("id", "viaje_id", "cupos_reservados"):
                exigir(isinstance(columns[name]["type"], Integer), f"{name} debe ser INT.")
            for name, length in (("pasajero_nombre", 150), ("estado", 20)):
                columnType = columns[name]["type"]
                exigir(
                    isinstance(columnType, NVARCHAR) and columnType.length == length,
                    f"{name} debe ser NVARCHAR({length}).",
                )
            exigir(
                columns["estado"]["type"].collation == "Latin1_General_100_BIN2",
                "El estado debe distinguir mayusculas de minusculas.",
            )
            dateType = columns["fecha_reserva"]["type"]
            # La reflexion del dialecto puede omitir la precision de DATETIME2.
            # Se comprueba el valor real del catalogo de SQL Server.
            datePrecision = connection.execute(
                text(
                    "SELECT DATETIME_PRECISION FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = :esquema AND TABLE_NAME = :tabla "
                    "AND COLUMN_NAME = :columna"
                ),
                {"esquema": "dbo", "tabla": "reservas", "columna": "fecha_reserva"},
            ).scalar_one()
            exigir(
                isinstance(dateType, DATETIME2) and datePrecision == 6,
                "fecha_reserva debe ser DATETIME2(6).",
            )
            exigir(
                "sysutcdatetime()" in (columns["fecha_reserva"]["default"] or "").lower(),
                "Falta el valor UTC predeterminado de fecha_reserva.",
            )
            identity = columns["id"].get("identity") or {}
            exigir(
                identity.get("start") == 1 and identity.get("increment") == 1,
                "id debe ser IDENTITY(1,1).",
            )
            primaryKey = inspector.get_pk_constraint("reservas", schema="dbo")
            exigir(primaryKey["constrained_columns"] == ["id"], "La PK debe ser id.")
            expectedChecks = {
                constraint.name
                for constraint in Reserva.__table__.constraints
                if isinstance(constraint, CheckConstraint)
            }
            # El dialecto MSSQL no implementa get_check_constraints().
            checkRows = connection.execute(
                text(
                    "SELECT name, is_disabled, is_not_trusted "
                    "FROM sys.check_constraints "
                    "WHERE parent_object_id = OBJECT_ID(N'dbo.reservas')"
                )
            ).mappings().all()
            actualChecks = {row["name"] for row in checkRows}
            exigir(expectedChecks <= actualChecks, "Faltan restricciones CHECK del modelo.")
            exigir(
                all(not row["is_disabled"] and not row["is_not_trusted"] for row in checkRows),
                "Hay restricciones deshabilitadas o no verificadas.",
            )
            indexes = inspector.get_indexes("reservas", schema="dbo")
            exigir(
                any(
                    index["name"] == "ix_reservas_viaje_estado"
                    and index["column_names"] == ["viaje_id", "estado"]
                    and not index["unique"]
                    for index in indexes
                ),
                "Falta el indice no unico de viaje y estado.",
            )
            exigir(
                not inspector.get_foreign_keys("reservas", schema="dbo"),
                "No debe haber claves foraneas hacia otros servicios.",
            )
            revision = MigrationContext.configure(
                connection, opts={"version_table_schema": "dbo"}
            ).get_current_revision()
            exigir(revision is not None, "Alembic no registra una revision aplicada.")
            total = connection.execute(select(func.count()).select_from(Reserva)).scalar_one()

        print("Estructura dbo.reservas correcta.")
        print("Seis columnas, tipos, IDENTITY, UTC, CHECK e indice verificados.")
        print(f"Revision Alembic: {revision}")
        print(f"Reservas cargadas: {total}")
        return 0
    except (ValidationError, SQLAlchemyError):
        print(
            "No se pudo verificar la estructura. Revisa .env, la conexion y "
            "la aplicacion de 'alembic upgrade head'.",
            file=sys.stderr,
        )
        return 1
    except ValueError as error:
        print(f"Estructura no valida: {error}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
