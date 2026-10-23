"""Crea dbo.reservas con sus restricciones e indice de consulta.

Revision ID: 0001_crear_reservas
Revises: ninguna
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = "0001_crear_reservas"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservas",
        sa.Column("id", sa.Integer(), sa.Identity(start=1, increment=1), nullable=False),
        sa.Column("viaje_id", sa.Integer(), nullable=False),
        sa.Column("pasajero_nombre", mssql.NVARCHAR(length=150), nullable=False),
        sa.Column("cupos_reservados", sa.Integer(), nullable=False),
        sa.Column(
            "estado",
            mssql.NVARCHAR(length=20, collation="Latin1_General_100_BIN2"),
            nullable=False,
        ),
        sa.Column(
            "fecha_reserva",
            mssql.DATETIME2(precision=6),
            server_default=sa.text("SYSUTCDATETIME()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reservas"),
        sa.CheckConstraint("viaje_id > 0", name="ck_reservas_viaje_id_positivo"),
        sa.CheckConstraint(
            "LEN(LTRIM(RTRIM(pasajero_nombre))) > 0",
            name="ck_reservas_pasajero_nombre_no_vacio",
        ),
        sa.CheckConstraint(
            "cupos_reservados >= 1", name="ck_reservas_cupos_reservados_minimo"
        ),
        sa.CheckConstraint(
            "estado IN (N'PENDIENTE', N'CONFIRMADA', N'CANCELADA') "
            "AND DATALENGTH(estado) = DATALENGTH(RTRIM(estado))",
            name="ck_reservas_estado_valido",
        ),
        schema="dbo",
    )
    op.create_index(
        "ix_reservas_viaje_estado",
        "reservas",
        ["viaje_id", "estado"],
        unique=False,
        schema="dbo",
    )


def downgrade() -> None:
    op.drop_index("ix_reservas_viaje_estado", table_name="reservas", schema="dbo")
    op.drop_table("reservas", schema="dbo")
