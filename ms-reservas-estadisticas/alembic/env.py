"""Entorno Alembic: configuracion desde .env y migraciones en SQL Server."""

from logging.config import fileConfig

from alembic import context

from app.config.database import buildDatabaseUrl, getEngine
from app.config.settings import getSettings
from app.models import Base
from app.models.reserva import UtcDateTime

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

targetMetadata = Base.metadata


def includeName(name, type_, parentNames):
    """Limita la inspeccion al esquema propio dbo de la base configurada."""

    if type_ == "schema":
        return name in (None, "dbo")
    if type_ == "table" and name == "alembic_version":
        # SQL Server refleja dbo como esquema por defecto (None). La tabla
        # tecnica no pertenece a los modelos ni debe proponerse para borrado.
        return False
    return True


def renderItem(type_, item, autogenContext):
    """Las migraciones guardan el tipo SQL, sin depender del conversor Python."""

    if type_ == "type" and isinstance(item, UtcDateTime):
        autogenContext.imports.add("from sqlalchemy.dialects import mssql")
        return "mssql.DATETIME2(precision=6)"
    return False


def runMigrationsOffline():
    """Genera SQL revisable sin abrir una conexion a la base."""

    context.configure(
        url=buildDatabaseUrl(getSettings()),
        target_metadata=targetMetadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="dbo",
        include_schemas=True,
        include_name=includeName,
        compare_type=True,
        compare_server_default=True,
        render_item=renderItem,
    )
    with context.begin_transaction():
        context.run_migrations()


def runMigrationsOnline():
    """Aplica o comprueba migraciones con el engine del microservicio."""

    engine = getEngine()
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=targetMetadata,
                version_table_schema="dbo",
                include_schemas=True,
                include_name=includeName,
                compare_type=True,
                compare_server_default=True,
                render_item=renderItem,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    runMigrationsOffline()
else:
    runMigrationsOnline()
