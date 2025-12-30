"""ensure command_rate_limits exists

Revision ID: f999b47ff238
Revises: 9422d49813ae
Create Date: 2025-12-31 01:44:15.507926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f999b47ff238'
down_revision: Union[str, Sequence[str], None] = '9422d49813ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
