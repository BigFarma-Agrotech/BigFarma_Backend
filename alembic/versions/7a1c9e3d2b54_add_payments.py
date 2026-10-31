"""add payments and order payment status

Revision ID: 7a1c9e3d2b54
Revises: 5d2b8e4f7a10
Create Date: 2026-10-31 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1c9e3d2b54'
down_revision: Union[str, Sequence[str], None] = '5d2b8e4f7a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Payments table, plus payment_status/payment_id on orders."""
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('subtotal', sa.Float(), nullable=False),
        sa.Column('delivery_fee', sa.Float(), nullable=False),
        sa.Column('tax', sa.Float(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('amount_kobo', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('gateway_response', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.create_index(op.f('ix_payments_reference'), 'payments', ['reference'], unique=True)
    op.create_index(op.f('ix_payments_user_id'), 'payments', ['user_id'], unique=False)

    # Orders placed before payments existed stay visible: mark them paid, then
    # make unpaid the default for everything placed through checkout
    op.add_column('orders', sa.Column('payment_status', sa.String(), nullable=False, server_default='paid'))
    with op.batch_alter_table('orders') as batch_op:
        batch_op.alter_column('payment_status', existing_type=sa.String(), server_default='unpaid')
        batch_op.add_column(sa.Column('payment_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_orders_payment_id_payments', 'payments', ['payment_id'], ['id'])
    op.create_index(op.f('ix_orders_payment_status'), 'orders', ['payment_status'], unique=False)
    op.create_index(op.f('ix_orders_payment_id'), 'orders', ['payment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_orders_payment_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_payment_status'), table_name='orders')
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_constraint('fk_orders_payment_id_payments', type_='foreignkey')
        batch_op.drop_column('payment_id')
        batch_op.drop_column('payment_status')
    op.drop_index(op.f('ix_payments_user_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_reference'), table_name='payments')
    op.drop_index(op.f('ix_payments_id'), table_name='payments')
    op.drop_table('payments')
