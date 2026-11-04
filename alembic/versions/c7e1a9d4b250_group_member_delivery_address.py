"""group members give a delivery address when joining

Revision ID: c7e1a9d4b250
Revises: a4f8c2e6d913
Create Date: 2026-11-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7e1a9d4b250'
down_revision: Union[str, Sequence[str], None] = 'a4f8c2e6d913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The farmer delivers each member's share to this address
    op.add_column('group_members', sa.Column('delivery_address', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('group_members', 'delivery_address')
