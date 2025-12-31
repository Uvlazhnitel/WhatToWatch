"""add unique constraint rec items

Revision ID: 31d4a3cbc0c5
Revises: f999b47ff238
Create Date: 2025-12-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '31d4a3cbc0c5'
down_revision = 'f999b47ff238'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate recommendation items
    # This ensures that for a given recommendation, we cannot have duplicate
    # (tmdb_id, position) pairs, which would indicate duplicate processing
    op.create_unique_constraint(
        'uq_rec_items_recommendation_tmdb_position',
        'agent_recommendation_items',
        ['recommendation_id', 'tmdb_id', 'position']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_rec_items_recommendation_tmdb_position',
        'agent_recommendation_items',
        type_='unique'
    )
