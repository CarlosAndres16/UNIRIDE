"""Crear dbo.conductores con los ocho campos del contrato.

Revision ID: 0001_crear_conductores
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = "0001_crear_conductores"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conductores",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), nullable=False),
        sa.Column("nombre", mssql.NVARCHAR(length=150), nullable=False),
        sa.Column("correo", mssql.NVARCHAR(length=254), nullable=False),
        sa.Column("password_hash", mssql.NVARCHAR(length=255), nullable=False),
        sa.Column("telefono", mssql.NVARCHAR(length=30), nullable=True),
        sa.Column("activo", mssql.BIT(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "fecha_creacion",
            mssql.DATETIME2(precision=6),
            server_default=sa.text("SYSUTCDATETIME()"),
            nullable=False,
        ),
        sa.Column(
            "fecha_actualizacion",
            mssql.DATETIME2(precision=6),
            server_default=sa.text("SYSUTCDATETIME()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conductores"),
        sa.UniqueConstraint("correo", name="uq_conductores_correo"),
        schema="dbo",
    )


def downgrade() -> None:
    op.drop_table("conductores", schema="dbo")
