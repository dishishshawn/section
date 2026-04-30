"""document_extraction_model

Adds Document.extraction_model so we can record (and choose per-upload)
which Claude model produced the extraction. Nullable — None means "use
the server default at extraction time" (controlled by the CLAUDE_MODEL
env var).

Revision ID: 0006_document_extraction_model
Revises: 0005_document_extraction_jobs
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_document_extraction_model"
down_revision: Union[str, None] = "0005_document_extraction_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extraction_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "extraction_model")
