"""add public ids to products, orders and group buys

Revision ID: 5d2b8e4f7a10
Revises: 3c7e9a1d5b42
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from utils.public_id import generate_public_id


# revision identifiers, used by Alembic.
revision: str = '5d2b8e4f7a10'
down_revision: Union[str, Sequence[str], None] = '3c7e9a1d5b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ['products', 'orders', 'group_buys']


def upgrade() -> None:
    """Add a random public_id to each table and fill it in for existing rows."""
    bind = op.get_bind()
    for table in TABLES:
        op.add_column(table, sa.Column('public_id', sa.String(length=8), nullable=True))

        rows = sa.table(table, sa.column('id', sa.Integer), sa.column('public_id', sa.String))
        ids = [row.id for row in bind.execute(sa.select(rows.c.id))]
        used = set()
        for row_id in ids:
            public_id = generate_public_id()
            while public_id in used:
                public_id = generate_public_id()
            used.add(public_id)
            bind.execute(rows.update().where(rows.c.id == row_id).values(public_id=public_id))

        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column('public_id', existing_type=sa.String(length=8), nullable=False)
        op.create_index(op.f(f'ix_{table}_public_id'), table, ['public_id'], unique=True)


def downgrade() -> None:
    """Remove the public ids."""
    for table in reversed(TABLES):
        op.drop_index(op.f(f'ix_{table}_public_id'), table_name=table)
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('public_id')
