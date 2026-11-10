"""estado civil del paciente (Res. 1995 de 1999)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10 21:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega la columna; los pacientes existentes quedan con estado civil vacío (NULL)."""
    op.add_column('pacientes', sa.Column('estado_civil', sa.String(length=15), nullable=True))


def downgrade() -> None:
    """Deshace el cambio (solo si fuera necesario volver a la versión anterior)."""
    op.drop_column('pacientes', 'estado_civil')
