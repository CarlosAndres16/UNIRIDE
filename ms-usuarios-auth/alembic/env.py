"""Alembic usa la misma configuración que la aplicación, sin secretos en INI."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config.database import Base, buildDatabaseUrl
from app.config.settings import getSettings
from app.models.conductor import Conductor  # noqa: F401: registra el modelo en metadata.


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def runMigrationsOffline() -> None:
    context.configure(
        url=buildDatabaseUrl(getSettings()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
        version_table_schema="dbo",
    )
    with context.begin_transaction():
        context.run_migrations()


def runMigrationsOnline() -> None:
    engine = create_engine(
        buildDatabaseUrl(getSettings()),
        poolclass=pool.NullPool,
        echo=False,
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_schemas=True,
                compare_type=True,
                version_table_schema="dbo",
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    runMigrationsOffline()
else:
    runMigrationsOnline()
