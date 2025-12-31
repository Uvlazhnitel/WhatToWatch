"""merge heads

Revision ID: 10684b2d1e3b
Revises: 31d4a3cbc0c5, 421de244c013
Create Date: 2025-12-31 00:09:04.201644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10684b2d1e3b'
down_revision: Union[str, Sequence[str], None] = ('31d4a3cbc0c5', '421de244c013')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
