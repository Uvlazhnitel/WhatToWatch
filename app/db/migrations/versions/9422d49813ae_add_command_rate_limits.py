"""add command rate limits

Revision ID: 9422d49813ae
Revises: 1c56c646669e
Create Date: 2025-12-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9422d49813ae'
down_revision = '1c56c646669e'
branch_labels = None
depends_on = None


def upgrade():
    # Check if the table already exists (migration branch reconciliation)
    # This handles the case where another migration branch already created this table
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'command_rate_limits' not in inspector.get_table_names():
        op.create_table(
            "command_rate_limits",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("command", sa.String(length=32), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("user_id", "command"),
        )

def downgrade():
    # Only drop if table exists (safe downgrade for branch reconciliation)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'command_rate_limits' in inspector.get_table_names():
        op.drop_table("command_rate_limits")
