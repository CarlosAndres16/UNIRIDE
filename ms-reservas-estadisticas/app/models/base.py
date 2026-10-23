"""Base declarativa compartida por los modelos propios del microservicio."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Expone los metadatos que Alembic utilizará para las migraciones."""
