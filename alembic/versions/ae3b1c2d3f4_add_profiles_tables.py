"""add_profiles_tables

Revision ID: ae3b1c2d3f4
Revises: 47d9f9f25c3e
Create Date: 2026-05-20 16:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ae3b1c2d3f4"
down_revision: Union[str, Sequence[str], None] = "47d9f9f25c3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("canonical_name", sa.String(), nullable=True),
        sa.Column("aliases", sa.JSON(), nullable=True),
        sa.Column("linked_entities", sa.JSON(), nullable=True),
        sa.Column("linked_accounts", sa.JSON(), nullable=True),
        sa.Column("source_services", sa.JSON(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_tier", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "profile_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "profile_id", sa.String(), sa.ForeignKey("profiles.id"), nullable=False
        ),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("profile_aliases")
    op.drop_table("profiles")
