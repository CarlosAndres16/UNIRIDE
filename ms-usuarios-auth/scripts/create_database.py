"""Crea únicamente la base configurada; el esquema se aplica con Alembic."""

from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config.database import buildDatabaseUrl
from app.config.settings import getSettings


def main() -> None:
    try:
        settings = getSettings()
    except ValidationError:
        raise SystemExit("Configuración inválida: complete las variables del archivo .env.") from None

    engine = create_engine(
        buildDatabaseUrl(settings, databaseName="master"),
        isolation_level="AUTOCOMMIT",
        echo=False,
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            databaseId = connection.scalar(
                text("SELECT DB_ID(:databaseName)"), {"databaseName": settings.DB_NAME}
            )
            if databaseId is not None:
                print("La base de datos configurada ya existe.")
                return
            databaseIdentifier = engine.dialect.identifier_preparer.quote(settings.DB_NAME)
            connection.exec_driver_sql(f"CREATE DATABASE {databaseIdentifier}")
            print("Base de datos creada. Aplique el esquema con: python -m alembic upgrade head")
    except SQLAlchemyError:
        raise SystemExit(
            "No se pudo crear la base. Revise SQL Server, ODBC, las variables DB_* "
            "y los permisos CREATE DATABASE del usuario configurado."
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
