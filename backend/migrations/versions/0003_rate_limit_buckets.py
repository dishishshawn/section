"""rate_limit_buckets

Adds the SQLite-backed token-bucket table that backs rate_limit.py. The
module already guards against a missing table via CREATE TABLE IF NOT EXISTS
(so the test fixture and older dev DBs keep working), but production should
own this table through Alembic so downgrades and inspection are possible.

Revision ID: 0003_rate_limit_buckets
Revises: 0002_stripe_webhook_events
Create Date: 2026-04-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_rate_limit_buckets"
down_revision: Union[str, None] = "0002_stripe_webhook_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.Float(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_buckets")
