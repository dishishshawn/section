"""initial schema snapshot

Faithful snapshot of the schema previously produced by the inline
CREATE TABLE / ALTER TABLE blocks in backend/main.py and by
Base.metadata.create_all() on the SQLAlchemy models.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("billing_status", sa.String(), nullable=True, server_default=sa.text("'trialing'")),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_id", "organizations", ["id"])
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # ------------------------------------------------------------------
    # projects
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("jurisdiction", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("owner_org", sa.String(), nullable=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_name", "projects", ["name"])

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("s3_key", sa.String(), nullable=True),
        sa.Column("mime", sa.String(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("ocr_status", sa.String(), nullable=True),
        sa.Column("extraction_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_documents_id", "documents", ["id"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])

    # ------------------------------------------------------------------
    # tracts
    # ------------------------------------------------------------------
    op.create_table(
        "tracts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("legal_description", sa.String(), nullable=True),
        sa.Column("gross_acres", sa.Float(), nullable=True),
    )
    op.create_index("ix_tracts_id", "tracts", ["id"])

    # ------------------------------------------------------------------
    # parties
    # ------------------------------------------------------------------
    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
    )
    op.create_index("ix_parties_id", "parties", ["id"])

    # ------------------------------------------------------------------
    # instruments
    # ------------------------------------------------------------------
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=True),
        sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
    )
    op.create_index("ix_instruments_id", "instruments", ["id"])

    # ------------------------------------------------------------------
    # interests
    # ------------------------------------------------------------------
    op.create_table(
        "interests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tract_id", sa.Integer(), sa.ForeignKey("tracts.id"), nullable=True),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("fraction_numerator", sa.Integer(), nullable=True),
        sa.Column("fraction_denominator", sa.Integer(), nullable=True),
        sa.Column("mineral_estate", sa.String(), nullable=True),
        sa.Column("burdens", sa.JSON(), nullable=True),
    )
    op.create_index("ix_interests_id", "interests", ["id"])

    # ------------------------------------------------------------------
    # obligations
    # ------------------------------------------------------------------
    op.create_table(
        "obligations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("params", sa.JSON(), nullable=True),
    )
    op.create_index("ix_obligations_id", "obligations", ["id"])

    # ------------------------------------------------------------------
    # fact_overrides
    # ------------------------------------------------------------------
    op.create_table(
        "fact_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("user_display", sa.String(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_index("ix_fact_overrides_id", "fact_overrides", ["id"])
    op.create_index(
        "ix_fact_overrides_lookup",
        "fact_overrides",
        ["entity_type", "entity_id", "field_name", "changed_at"],
    )

    # ------------------------------------------------------------------
    # org_memberships
    # ------------------------------------------------------------------
    op.create_table(
        "org_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default=sa.text("'member'")),
        sa.Column("joined_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("user_id", "org_id", name="uq_user_org"),
    )
    op.create_index("ix_org_memberships_id", "org_memberships", ["id"])

    # ------------------------------------------------------------------
    # project_access
    # ------------------------------------------------------------------
    op.create_table(
        "project_access",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("role", sa.String(), nullable=False, server_default=sa.text("'viewer'")),
        sa.Column("granted_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.Column("granted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("user_id", "project_id", name="uq_user_project"),
    )
    op.create_index("ix_project_access_id", "project_access", ["id"])

    # ------------------------------------------------------------------
    # org_invites
    # ------------------------------------------------------------------
    op.create_table(
        "org_invites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("invited_email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default=sa.text("'member'")),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("project_role", sa.String(), nullable=True),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("invited_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("token", name="uq_org_invites_token"),
    )
    op.create_index("ix_org_invites_id", "org_invites", ["id"])
    op.create_index("ix_org_invites_token", "org_invites", ["token"], unique=True)
    op.create_index("ix_org_invites_invited_email", "org_invites", ["invited_email"])


def downgrade() -> None:
    op.drop_index("ix_org_invites_invited_email", table_name="org_invites")
    op.drop_index("ix_org_invites_token", table_name="org_invites")
    op.drop_index("ix_org_invites_id", table_name="org_invites")
    op.drop_table("org_invites")

    op.drop_index("ix_project_access_id", table_name="project_access")
    op.drop_table("project_access")

    op.drop_index("ix_org_memberships_id", table_name="org_memberships")
    op.drop_table("org_memberships")

    op.drop_index("ix_fact_overrides_lookup", table_name="fact_overrides")
    op.drop_index("ix_fact_overrides_id", table_name="fact_overrides")
    op.drop_table("fact_overrides")

    op.drop_index("ix_obligations_id", table_name="obligations")
    op.drop_table("obligations")

    op.drop_index("ix_interests_id", table_name="interests")
    op.drop_table("interests")

    op.drop_index("ix_instruments_id", table_name="instruments")
    op.drop_table("instruments")

    op.drop_index("ix_parties_id", table_name="parties")
    op.drop_table("parties")

    op.drop_index("ix_tracts_id", table_name="tracts")
    op.drop_table("tracts")

    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_index("ix_documents_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_index("ix_projects_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_index("ix_organizations_id", table_name="organizations")
    op.drop_table("organizations")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
