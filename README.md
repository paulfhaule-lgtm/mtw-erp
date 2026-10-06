# MTW ERP v2 — Projects, Accounts, Payroll & Invoicing

This version expands the original Accounts Officer app into a project-based ERP for Metal & Timber Works.

## Included
- Login with Railway/PostgreSQL support
- Dashboard with day/week/month/year income, expenses and net
- Projects / Job Cards
- Multiple fundi/staff per project, each with job, agreed amount, paid amount and balance
- Project materials requested/used, quantities, suppliers, paid and balance
- Fundi/staff loans and advances with outstanding balances
- Payroll with gross, loan deductions, other deductions, net, paid and balance
- Office and project operating expenses in one transaction ledger
- Income and expense reports by period and category
- Project expense reporting
- Invoice creation with multiple line items, tax rate, company details and PDF download
- Company settings: logo, address, phone, email, TIN, VRN, invoice prefix
- Railway-ready Docker deployment

## Railway variables
Set `SECRET_KEY`, `ACCOUNTS_PASSWORD`, and use the PostgreSQL `DATABASE_URL` supplied by Railway.

## Login
Username: `accounts`
Password: value of `ACCOUNTS_PASSWORD`.

## Important
For production, use a strong secret/password and enable HTTPS through Railway.
