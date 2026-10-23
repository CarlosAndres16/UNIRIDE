"""Conexión diferida a la base de datos propia del microservicio."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, getSettings


def buildDatabaseUrl(settings: Settings) -> URL:
    """Construye la URL sin concatenar ni registrar credenciales.

    TrustServerCertificate se admite aquí para el SQL Server de desarrollo
    local. Un despliegue con certificados confiables debe dejar de usarlo.
    """

    return URL.create(
        "mssql+pyodbc",
        username=settings.dbUser,
        password=settings.dbPassword.get_secret_value(),
        host=settings.dbHost,
        port=settings.dbPort,
        database=settings.dbName,
        query={
            "driver": settings.dbDriver,
            "Encrypt": "yes",
            "TrustServerCertificate": "yes",
        },
    )


@lru_cache(maxsize=1)
def getEngine() -> Engine:
    """Crea el engine al solicitarlo; la conexión se abre al utilizarlo."""

    return create_engine(
        buildDatabaseUrl(getSettings()),
        pool_pre_ping=True,
        echo=False,
        hide_parameters=True,
        connect_args={"timeout": 5},
    )


@lru_cache(maxsize=1)
def getSessionFactory() -> sessionmaker[Session]:
    """Prepara sesiones sin abrir conexiones durante la importación."""

    return sessionmaker(
        bind=getEngine(),
        autoflush=False,
        expire_on_commit=False,
    )


def getSession() -> Iterator[Session]:
    """Entrega una sesión y la cierra al terminar su uso."""

    with getSessionFactory()() as session:
        yield session
