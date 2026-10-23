"""Prepara la base y una cuenta SQL local mediante autenticacion Windows.

Ejecutar una vez con una cuenta Windows administradora de SQL Server:
    python -m scripts.preparar_base_datos

No cambia el modo de autenticacion ni reinicia SQL Server. No crea tablas.
"""

import sys

from pydantic import ValidationError
from sqlalchemy import Unicode, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import DDL

from app.config.settings import getSettings


def main() -> int:
    try:
        settings = getSettings()
    except ValidationError:
        print("Configuracion incompleta. Revisa las variables DB_* de .env.", file=sys.stderr)
        return 1

    # El administrador entra con Windows. La cuenta de la aplicacion usara
    # DB_USER/DB_PASSWORD; no hereda los privilegios de este administrador.
    adminUrl = URL.create(
        "mssql+pyodbc",
        host=settings.dbHost,
        port=settings.dbPort,
        database="master",
        query={
            "driver": settings.dbDriver,
            "Encrypt": "yes",
            "TrustServerCertificate": "yes",
        },
    )
    adminEngine = create_engine(
        adminUrl,
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
        connect_args={"timeout": 5},
    )

    try:
        with adminEngine.connect() as connection:
            windowsOnly = connection.execute(
                text("SELECT CAST(SERVERPROPERTY('IsIntegratedSecurityOnly') AS int)")
            ).scalar_one()

            # DDL no admite parametros para identificadores o CREATE LOGIN.
            # SQLAlchemy delimita los identificadores y escapa el literal de
            # contrasena; nunca se insertan valores sin escapar en las plantillas.
            preparer = connection.dialect.identifier_preparer
            compiler = connection.dialect.statement_compiler(connection.dialect, None)
            context = {
                "base": preparer.quote_identifier(settings.dbName),
                "usuario": preparer.quote_identifier(settings.dbUser),
                "clave": compiler.render_literal_value(
                    settings.dbPassword.get_secret_value(), Unicode()
                ),
            }

            if connection.execute(
                text("SELECT DB_ID(:nombre)"), {"nombre": settings.dbName}
            ).scalar_one() is None:
                connection.execute(DDL("CREATE DATABASE %(base)s", context=context))
                print("Base de datos creada.")
            else:
                print("La base de datos ya existe; se conserva.")

            if connection.execute(
                text("SELECT SUSER_ID(:usuario)"), {"usuario": settings.dbUser}
            ).scalar_one() is None:
                connection.execute(
                    DDL(
                        "CREATE LOGIN %(usuario)s WITH PASSWORD = %(clave)s, "
                        "DEFAULT_DATABASE = %(base)s, CHECK_POLICY = ON",
                        context=context,
                    )
                )
                print("Login SQL creado.")
            else:
                print("El login ya existe; se conserva su contrasena.")

            connection.execute(DDL("USE %(base)s", context=context))
            if connection.execute(
                text("SELECT USER_ID(:usuario)"), {"usuario": settings.dbUser}
            ).scalar_one() is None:
                connection.execute(
                    DDL("CREATE USER %(usuario)s FOR LOGIN %(usuario)s", context=context)
                )

            # Permisos locales para consultas, seed y las futuras migraciones.
            # No se otorgan roles de servidor ni acceso a bases ajenas.
            for role in ("db_datareader", "db_datawriter", "db_ddladmin"):
                if not connection.execute(
                    text("SELECT IS_ROLEMEMBER(:rol, :usuario)"),
                    {"rol": role, "usuario": settings.dbUser},
                ).scalar_one():
                    connection.execute(
                        DDL(
                            "ALTER ROLE %(rol)s ADD MEMBER %(usuario)s",
                            context={**context, "rol": preparer.quote_identifier(role)},
                        )
                    )

        print("Preparacion completada. No se han creado tablas.")
        if windowsOnly:
            print(
                "Pendiente: la instancia solo admite Windows. La cuenta SQL no "
                "podra conectarse hasta autorizar y habilitar el modo mixto."
            )
        return 0
    except SQLAlchemyError:
        # Una excepcion de DDL puede contener el literal de CREATE LOGIN.
        # No mostrar su representacion ni el SQL para proteger la contrasena.
        print(
            "No se pudo preparar la base. Comprueba que tu cuenta Windows sea "
            "administradora de SQL Server y que DB_HOST/DB_DRIVER sean correctos.",
            file=sys.stderr,
        )
        return 1
    finally:
        adminEngine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
