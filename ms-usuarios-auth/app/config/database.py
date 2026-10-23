"""Conexiones SQL Server diferidas: importar la app no abre conexiones."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config.settings import Settings, getSettings


class Base(DeclarativeBase):
    pass


def buildDatabaseUrl(settings: Settings, databaseName: str | None = None) -> URL:
    return URL.create(
        drivername="mssql+pyodbc",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=databaseName if databaseName is not None else settings.DB_NAME,
        query={
            "driver": settings.DB_DRIVER,
            "Encrypt": "yes",
            "TrustServerCertificate": "yes",
        },
    )


@lru_cache(maxsize=1)
def getEngine() -> Engine:
    return create_engine(
        buildDatabaseUrl(getSettings()),
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
    )


def getSession() -> Generator[Session, None, None]:
    with Session(getEngine(), expire_on_commit=False) as session:
        yield session
