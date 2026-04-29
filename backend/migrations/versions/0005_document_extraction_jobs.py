"""document_extraction_jobs

Adds durable extraction job status metadata for Redis/RQ-backed processing.

Revision ID: 0005_document_extraction_jobs
Revises: 0004_email_verification_codes
Create Date: 2026-04-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_document_extraction_jobs"
down_revision: Union[str, None] = "0004_email_verification_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extraction_job_id", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("extraction_warning", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("extraction_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_documents_extraction_job_id", "documents", ["extraction_job_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_extraction_job_id", table_name="documents")
    op.drop_column("documents", "extraction_attempts")
    op.drop_column("documents", "extraction_warning")
    op.drop_column("documents", "extraction_error")
    op.drop_column("documents", "extraction_job_id")
