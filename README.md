# MTW ERP — Accounts Officer Edition

A focused accounting ERP for Metal and Timber Works.

## Scope
Only one role: **Accounts Officer**.

It records:
- Income
- Expenses
- Payments
- Cash, bank, mobile money and cheque transactions
- Categories
- Project references
- Daily, weekly, monthly and yearly totals
- Income vs expense and net balance
- Category reports
- CSV export

## Railway
Set:
- `SECRET_KEY`
- `DATABASE_URL`
- `ACCOUNTS_PASSWORD`

Railway PostgreSQL should provide `DATABASE_URL`.

Login:
- Username: `accounts`
- Password: value of `ACCOUNTS_PASSWORD`

Do not commit real passwords or `.env`.
