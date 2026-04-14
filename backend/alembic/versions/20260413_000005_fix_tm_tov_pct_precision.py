"""fix tm_tov_pct column precision from Numeric(5,3) to Numeric(5,1)

TM_TOV_PCT is a percentage (0-100) but was created as Numeric(5,3) which
maxes at 99.999. Players with 100% turnover rate (edge case in small samples)
cause overflow. Widen to Numeric(5,1) to support values up to 9999.9.

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2026-04-13 00:00:05.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g8h9i0j1k2l3'
down_revision: Union[str, None] = 'f7g8h9i0j1k2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'player_advanced_stats',
        'tm_tov_pct',
        type_=sa.Numeric(5, 1),
        existing_type=sa.Numeric(5, 3),
    )


def downgrade() -> None:
    op.alter_column(
        'player_advanced_stats',
        'tm_tov_pct',
        type_=sa.Numeric(5, 3),
        existing_type=sa.Numeric(5, 1),
    )
