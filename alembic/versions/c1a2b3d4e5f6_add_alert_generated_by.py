"""add_alert_generated_by

Revision ID: c1a2b3d4e5f6
Revises: b7c9e1f6a2c
Create Date: 2026-05-20 17:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "b7c9e1f6a2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("generated_by", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "generated_by")
