"""Comprueba SQL Server sin crear bases de datos, tablas ni datos."""

import re
import sys

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config.database import getEngine
from app.config.settings import getSettings


def getSqlState(error: SQLAlchemyError) -> str | None:
    """Extrae solo un código ODBC válido, sin copiar mensajes del proveedor."""

    originalError = getattr(error, "orig", None)
    arguments = getattr(originalError, "args", ())
    if arguments and isinstance(arguments[0], str):
        candidate = arguments[0]
        if re.fullmatch(r"[A-Z0-9]{5}", candidate):
            return candidate
    return None


def main() -> int:
    """Devuelve cero únicamente después de ejecutar una consulta real."""

    try:
        getSettings()
        engine = getEngine()
        try:
            with engine.connect() as connection:
                result = connection.execute(
                    text(
                        """
                        SELECT
                            DB_NAME() AS database_name,
                            ORIGINAL_LOGIN() AS login_name,
                            CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(128))
                                AS server_version,
                            (
                                SELECT COUNT(*)
                                FROM sys.tables
                                WHERE is_ms_shipped = 0
                            ) AS user_table_count
                        """
                    )
                ).mappings().one()
        finally:
            engine.dispose()
    except ValidationError as error:
        fields = sorted(
            {
                str(detail["loc"][0])
                for detail in error.errors(
                    include_input=False,
                    include_context=False,
                    include_url=False,
                )
                if detail["loc"]
            }
        )
        print(
            "Configuración inválida. Revisa estas variables del entorno o .env: "
            + ", ".join(fields),
            file=sys.stderr,
        )
        return 1
    except SQLAlchemyError as error:
        sqlState = getSqlState(error)
        suggestions = {
            "28000": (
                "Revisa DB_USER, DB_PASSWORD, los permisos sobre DB_NAME y que "
                "la instancia admita autenticación SQL (modo mixto)."
            ),
            "08001": "Revisa DB_HOST, DB_PORT y que SQL Server acepte conexiones TCP.",
            "08004": "Revisa que DB_NAME exista y que el usuario tenga acceso.",
            "HYT00": "SQL Server no respondió dentro del tiempo de conexión permitido.",
            "HYT01": "Se agotó el tiempo de conexión; revisa servidor y puerto.",
            "IM002": "Comprueba que DB_DRIVER corresponda a un controlador ODBC instalado.",
        }
        message = suggestions.get(
            sqlState,
            "Revisa el servicio SQL Server, el controlador ODBC y la configuración de .env.",
        )
        code = f" (ODBC {sqlState})" if sqlState else ""
        print(f"No se pudo verificar la conexión{code}. {message}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "No se pudo verificar la conexión. Comprueba las dependencias y la configuración de .env.",
            file=sys.stderr,
        )
        return 1

    print("Conexión SQL Server correcta.")
    print(f"Base de datos: {result['database_name']}")
    print(f"Usuario SQL autenticado: {result['login_name']}")
    print(f"Versión SQL Server: {result['server_version']}")
    print(f"Tablas de usuario en esta base: {result['user_table_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
