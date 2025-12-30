from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "command_rate_limits",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command", sa.String(length=32), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "command"),
    )

def downgrade():
    op.drop_table("command_rate_limits")
