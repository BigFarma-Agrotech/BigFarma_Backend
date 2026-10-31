"""group buy payments: payment purpose, member contact, group bulk orders

Revision ID: 9c3e5a7b2d81
Revises: 8b2d4f6a1c37
Create Date: 2026-10-31 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c3e5a7b2d81'
down_revision: Union[str, Sequence[str], None] = '8b2d4f6a1c37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('payments') as batch_op:
        batch_op.add_column(sa.Column('purpose', sa.String(), nullable=False, server_default='order'))
        batch_op.add_column(sa.Column('group_member_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('group_quantity', sa.Float(), nullable=True))
        batch_op.create_foreign_key('fk_payments_group_member_id', 'group_members', ['group_member_id'], ['id'])
    op.create_index(op.f('ix_payments_group_member_id'), 'payments', ['group_member_id'], unique=False)

    with op.batch_alter_table('group_buys') as batch_op:
        batch_op.add_column(sa.Column('min_member_quantity', sa.Float(), nullable=False, server_default='1'))

    with op.batch_alter_table('group_members') as batch_op:
        batch_op.add_column(sa.Column('contact_name', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('contact_phone', sa.String(), nullable=True))

    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_orders_group_id', 'group_buys', ['group_id'], ['id'])
    op.create_index(op.f('ix_orders_group_id'), 'orders', ['group_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_orders_group_id'), table_name='orders')
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_constraint('fk_orders_group_id', type_='foreignkey')
        batch_op.drop_column('group_id')
    with op.batch_alter_table('group_members') as batch_op:
        batch_op.drop_column('contact_phone')
        batch_op.drop_column('contact_name')
    with op.batch_alter_table('group_buys') as batch_op:
        batch_op.drop_column('min_member_quantity')
    op.drop_index(op.f('ix_payments_group_member_id'), table_name='payments')
    with op.batch_alter_table('payments') as batch_op:
        batch_op.drop_constraint('fk_payments_group_member_id', type_='foreignkey')
        batch_op.drop_column('group_quantity')
        batch_op.drop_column('group_member_id')
        batch_op.drop_column('purpose')
