"""add embeddings tables

Revision ID: df44363c6004
Revises: <PUT_PREVIOUS_REVISION_ID_HERE>
Create Date: 2025-12-30
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

# revision identifiers, used by Alembic.
revision = "df44363c6004"
down_revision = "671594a2e361"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # если у тебя уже включается vector в env.py — можно оставить, но лишним не будет
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "text_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("embedding", VECTOR(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_type IN ('review','film_meta','profile')", name="chk_text_embeddings_source_type"),
    )
    op.create_index("ux_text_embeddings_user_source", "text_embeddings", ["user_id", "source_type", "source_id"], unique=True)
    op.create_index("ix_text_embeddings_user_type", "text_embeddings", ["user_id", "source_type"], unique=False)

    op.create_table(
        "embedding_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_type IN ('review','film_meta','profile')", name="chk_embedding_jobs_source_type"),
        sa.CheckConstraint("status IN ('pending','processing','done','failed')", name="chk_embedding_jobs_status"),
    )
    op.create_index("ux_embedding_jobs_user_source", "embedding_jobs", ["user_id", "source_type", "source_id"], unique=True)
    op.create_index("ix_embedding_jobs_status", "embedding_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_embedding_jobs_status", table_name="embedding_jobs")
    op.drop_index("ux_embedding_jobs_user_source", table_name="embedding_jobs")
    op.drop_table("embedding_jobs")

    op.drop_index("ix_text_embeddings_user_type", table_name="text_embeddings")
    op.drop_index("ux_text_embeddings_user_source", table_name="text_embeddings")
    op.drop_table("text_embeddings")
