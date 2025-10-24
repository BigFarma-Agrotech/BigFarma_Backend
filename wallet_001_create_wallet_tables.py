"""create wallet tables

Revision ID: wallet_001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'wallet_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create wallet table
    op.create_table('wallets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('farmer_id', sa.Integer(), nullable=False),
        sa.Column('balance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('ledger_balance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='NGN'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_transaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['farmer_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('farmer_id')
    )
    op.create_index(op.f('ix_wallets_farmer_id'), 'wallets', ['farmer_id'], unique=True)

    # Create bank_accounts table
    op.create_table('bank_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('wallet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_number', sa.String(20), nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column('bank_code', sa.String(10), nullable=False),
        sa.Column('bank_name', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('pending', 'verified', 'failed', name='bankaccountstatus'), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verification_reference', sa.String(255), nullable=True),
        sa.Column('recipient_code', sa.String(255), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wallet_id', 'account_number', 'bank_code', name='_wallet_account_bank_uc')
    )
    op.create_index(op.f('ix_bank_accounts_wallet_id'), 'bank_accounts', ['wallet_id'], unique=False)

    # Create withdrawal_requests table
    op.create_table('withdrawal_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('wallet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bank_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('fee', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('final_amount', sa.Float(), nullable=False),
        sa.Column('reference', sa.String(100), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'cancelled', name='withdrawalstatus'), nullable=False),
        sa.Column('gateway_reference', sa.String(255), nullable=True),
        sa.Column('gateway_response', sa.Text(), nullable=True),
        sa.Column('initiated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id'], ),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference'),
        sa.UniqueConstraint('idempotency_key')
    )
    op.create_index(op.f('ix_withdrawal_requests_wallet_id'), 'withdrawal_requests', ['wallet_id'], unique=False)
    op.create_index(op.f('ix_withdrawal_requests_status'), 'withdrawal_requests', ['status'], unique=False)

    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('wallet_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reference', sa.String(100), nullable=False),
        sa.Column('type', sa.Enum('credit', 'debit', name='transactiontype'), nullable=False),
        sa.Column('category', sa.Enum('product_sale', 'investment_payout', 'withdrawal', 'deposit', 'refund', 'bonus', name='transactioncategory'), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('balance_before', sa.Float(), nullable=False),
        sa.Column('balance_after', sa.Float(), nullable=False),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='completed'),
        sa.Column('product_order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('investment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('withdrawal_request_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['withdrawal_request_id'], ['withdrawal_requests.id'], ),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference')
    )
    op.create_index(op.f('ix_transactions_wallet_id'), 'transactions', ['wallet_id'], unique=False)
    op.create_index(op.f('ix_transactions_type'), 'transactions', ['type'], unique=False)
    op.create_index(op.f('ix_transactions_category'), 'transactions', ['category'], unique=False)
    op.create_index(op.f('ix_transactions_created_at'), 'transactions', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order due to foreign key constraints
    op.drop_index(op.f('ix_transactions_created_at'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_category'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_type'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_wallet_id'), table_name='transactions')
    op.drop_table('transactions')

    op.drop_index(op.f('ix_withdrawal_requests_status'), table_name='withdrawal_requests')
    op.drop_index(op.f('ix_withdrawal_requests_wallet_id'), table_name='withdrawal_requests')
    op.drop_table('withdrawal_requests')

    op.drop_index(op.f('ix_bank_accounts_wallet_id'), table_name='bank_accounts')
    op.drop_table('bank_accounts')

    op.drop_index(op.f('ix_wallets_farmer_id'), table_name='wallets')
    op.drop_table('wallets')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS transactiontype')
    op.execute('DROP TYPE IF EXISTS transactioncategory')
    op.execute('DROP TYPE IF EXISTS withdrawalstatus')
    op.execute('DROP TYPE IF EXISTS bankaccountstatus')
