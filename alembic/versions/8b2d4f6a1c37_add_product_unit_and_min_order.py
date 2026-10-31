"""add product unit and minimum order quantity

Revision ID: 8b2d4f6a1c37
Revises: 7a1c9e3d2b54
Create Date: 2026-10-31 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from utils.units import parse_quantity


# revision identifiers, used by Alembic.
revision: str = '8b2d4f6a1c37'
down_revision: Union[str, Sequence[str], None] = '7a1c9e3d2b54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('unit', sa.String(), nullable=True))
    op.add_column('products', sa.Column('min_order_quantity', sa.Float(), nullable=False, server_default='1'))

    # Existing products: take the unit from the stock text ("100 kg" -> "kg",
    # "20 bags" -> "bag"); the minimum order stays 1
    bind = op.get_bind()
    products = sa.table('products', sa.column('id', sa.Integer), sa.column('quantity', sa.String),
                        sa.column('unit', sa.String))
    for row in bind.execute(sa.select(products.c.id, products.c.quantity)).all():
        _, unit = parse_quantity(row.quantity)
        if unit:
            bind.execute(products.update().where(products.c.id == row.id).values(unit=unit))


def downgrade() -> None:
    with op.batch_alter_table('products') as batch_op:
        batch_op.drop_column('min_order_quantity')
        batch_op.drop_column('unit')
