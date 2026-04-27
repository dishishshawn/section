"""stripe_webhook_events + stripe_customer_id index

Adds the idempotency ledger table for Stripe webhooks and an index on
organizations.stripe_customer_id to support the customer-id fallback lookup.

Revision ID: 0002_stripe_webhook_events
Revises: 0001_initial
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_stripe_webhook_events"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("payload_hash", sa.String(), nullable=True),
        sa.UniqueConstraint("event_id", name="uq_stripe_webhook_events_event_id"),
    )
    op.create_index("ix_stripe_webhook_events_id", "stripe_webhook_events", ["id"])
    op.create_index(
        "ix_stripe_webhook_events_event_id",
        "stripe_webhook_events",
        ["event_id"],
        unique=True,
    )

    # Index stripe_customer_id on organizations for the webhook fallback lookup.
    op.create_index(
        "ix_organizations_stripe_customer_id",
        "organizations",
        ["stripe_customer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_stripe_customer_id", table_name="organizations")
    op.drop_index("ix_stripe_webhook_events_event_id", table_name="stripe_webhook_events")
    op.drop_index("ix_stripe_webhook_events_id", table_name="stripe_webhook_events")
    op.drop_table("stripe_webhook_events")
