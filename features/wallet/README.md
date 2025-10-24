# Wallet Feature

The wallet feature provides comprehensive financial management for farmers on the BigFarma platform. It handles balance management, transactions, withdrawals, and bank account verification.

## Features

- **Wallet Management**: Automatic wallet creation and balance tracking
- **Transaction History**: Complete audit trail of all financial activities
- **Withdrawals**: Secure withdrawal processing with minimum limits and fee calculation
- **Bank Account Verification**: Real-time bank account verification before adding
- **Multi-Bank Support**: Support for all major Nigerian banks
- **Idempotency**: Duplicate request prevention for withdrawals
- **Real-time Updates**: Instant balance updates after transactions

## Architecture

### Models
- `Wallet`: Core wallet entity with balance tracking
- `Transaction`: Immutable transaction records
- `WithdrawalRequest`: Withdrawal request tracking
- `BankAccount`: Verified bank accounts

### Services
- `WalletService`: Core wallet operations (credit, debit, balance)
- `WithdrawalService`: Withdrawal processing and management
- `BankVerificationService`: Bank account verification and management

### API Endpoints

#### Wallet Operations
- `GET /api/wallet/balance` - Get current wallet balance
- `GET /api/wallet/dashboard` - Get comprehensive dashboard data
- `GET /api/wallet/transactions` - Get paginated transaction history

#### Withdrawal Operations
- `POST /api/wallet/withdraw` - Initiate withdrawal request
- `GET /api/wallet/withdrawal/{id}` - Check withdrawal status
- `POST /api/wallet/withdrawal/{id}/cancel` - Cancel pending withdrawal

#### Bank Account Operations
- `POST /api/wallet/bank-accounts/verify` - Verify bank account
- `POST /api/wallet/bank-accounts` - Add verified bank account
- `GET /api/wallet/bank-accounts` - List all bank accounts
- `PUT /api/wallet/bank-accounts/{id}/primary` - Set primary account

## Integration Points

### For Product Sales
```python
from features.wallet.integration import WalletIntegration

# When a product is sold
WalletIntegration.credit_for_product_sale(
    db=db_session,
    farmer_id=farmer.id,
    amount=1500.00,
    product_name="Fresh Tomatoes",
    order_id=order.id
)
```

### For Investment Payouts
```python
# When investment returns are paid
WalletIntegration.credit_for_investment_payout(
    db=db_session,
    farmer_id=farmer.id,
    amount=50000.00,
    investment_title="Poultry Farm Q1 2024",
    investment_id=investment.id,
    payout_type="returns"
)
```

## Business Rules

### Withdrawals
- Minimum withdrawal amount: ₦500
- Withdrawal fee: 1.5% (capped at ₦1,000)
- Only one pending withdrawal allowed at a time
- Bank account must be verified before withdrawal

### Transactions
- All transactions are immutable once created
- Balance updates are atomic and consistent
- Transaction references are unique and trackable

### Bank Accounts
- Account number must be 10 digits
- Duplicate accounts are prevented
- First added account becomes primary by default
- Only verified accounts can receive withdrawals

## Error Handling

The wallet feature includes comprehensive error handling:
- `InsufficientFundsError`: When withdrawal exceeds available balance
- `WithdrawalLimitError`: When amount violates minimum/maximum limits
- `PendingWithdrawalError`: When user has existing pending withdrawal
- `BankAccountVerificationError`: When bank verification fails
- `DuplicateBankAccountError`: When adding duplicate account

## Security Considerations

- Database transactions ensure atomic operations
- Idempotency keys prevent duplicate withdrawals
- Bank accounts are verified before adding
- All financial operations are logged
- Sensitive data (bank details) are encrypted at rest

## Configuration

Key configuration options in `config.py`:
- `MINIMUM_WITHDRAWAL_AMOUNT`: Minimum withdrawal limit
- `WITHDRAWAL_FEE_PERCENTAGE`: Fee percentage for withdrawals
- `PAYMENT_GATEWAY_PROVIDER`: Payment gateway integration
- `SEND_WITHDRAWAL_SMS/EMAIL`: Notification preferences

## Testing

To test the wallet feature:

```python
# Create a test wallet
wallet = wallet_service.create_wallet(farmer_id)

# Credit the wallet
transaction = wallet_service.credit_wallet(
    wallet_id=wallet.id,
    amount=10000.00,
    category=TransactionCategory.PRODUCT_SALE,
    description="Test credit"
)

# Check balance
balance = wallet_service.get_wallet_balance(farmer_id)
assert balance["ledger_balance"] == 10000.00
```

## Future Enhancements

- [ ] Scheduled withdrawals
- [ ] Multi-currency support
- [ ] Withdrawal limits per time period
- [ ] 2FA for large withdrawals
- [ ] Bulk withdrawal processing
- [ ] Investment wallet separation
- [ ] Savings goals and targets
- [ ] Transaction categories and analytics

## Dependencies

- SQLAlchemy for database operations
- Pydantic for data validation
- FastAPI for API endpoints
- Payment gateway SDK (Paystack/Flutterwave)

## Migration

To add the wallet tables to your database:

```sql
-- Run migrations to create wallet tables
alembic upgrade head
```

Make sure to update your User model to include the wallet relationship:
```python
wallet = relationship("Wallet", back_populates="farmer", uselist=False)
```
