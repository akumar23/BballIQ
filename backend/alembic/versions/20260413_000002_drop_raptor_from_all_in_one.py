"""drop raptor columns from player_all_in_one_metrics

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-04-13 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7g8h9i0'
down_revision: Union[str, None] = 'c4d5e6f7g8h9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('player_all_in_one_metrics', 'raptor')
    op.drop_column('player_all_in_one_metrics', 'raptor_offense')
    op.drop_column('player_all_in_one_metrics', 'raptor_defense')


def downgrade() -> None:
    op.add_column('player_all_in_one_metrics', sa.Column('raptor', sa.Numeric(6, 2), nullable=True))
    op.add_column('player_all_in_one_metrics', sa.Column('raptor_offense', sa.Numeric(6, 2), nullable=True))
    op.add_column('player_all_in_one_metrics', sa.Column('raptor_defense', sa.Numeric(6, 2), nullable=True))
