"""Final cleanup and cities

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-03-05 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add city to plans
    op.add_column('plans', sa.Column('city', sa.String(length=20), nullable=True))

    # 2. Recreate management_expenses
    # Drop the old one first (it was added in b2c3d4e5f6a7)
    op.drop_table('management_expenses')
    op.create_table(
        'management_expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('city', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_management_expenses_date', 'management_expenses', ['date'])

    # 3. Drop adjustments (debts)
    op.drop_table('adjustments')


def downgrade() -> None:
    # 1. Recreate adjustments
    op.create_table('adjustments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_paid', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 2. Recreate old management_expenses
    op.drop_table('management_expenses')
    op.create_table(
        'management_expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('month', sa.String(7), nullable=False),
        sa.Column('consumables', sa.Float(), nullable=False, server_default='0'),
        sa.Column('rent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('equipment', sa.Float(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_management_expenses_month', 'management_expenses', ['month'])

    # 3. Drop column from plans
    op.drop_column('plans', 'city')
