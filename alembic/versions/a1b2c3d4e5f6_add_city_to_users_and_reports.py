"""Add city to users and reports

Revision ID: a1b2c3d4e5f6
Revises: 2e1ad89ccbb9
Create Date: 2026-03-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2e1ad89ccbb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('city', sa.String(20), nullable=True))
    op.add_column('reports', sa.Column('city', sa.String(20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reports', 'city')
    op.drop_column('users', 'city')
