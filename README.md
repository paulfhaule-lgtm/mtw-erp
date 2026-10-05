# MTW ERP Web Deployment Package

## What this is
A deployable web ERP starter for Metal & Timber Works Co Ltd. It uses Flask + PostgreSQL + Nginx and a daily PostgreSQL backup container.

## Four users
- accounts / accounts123 — Accounts + Sales/Reception
- production / production123 — Production Director + Production
- store / store123 — Store Keeper + Procurement
- md / md123 — Managing Director

Change passwords before real use.

## Deploy on Ubuntu VPS
1. Install Docker and Docker Compose plugin.
2. Copy this folder to the VPS.
3. `cp .env.example .env`
4. Edit `.env` and set strong random DB_PASSWORD and SECRET_KEY.
5. Run `docker compose up -d --build`
6. Open the server IP in a browser.

## Automatic backup
The backup service makes a compressed PostgreSQL dump every 24 hours into `./backups` and removes local backups older than 30 days.

For real production, copy backups to a SECOND cloud storage/server (not the same VPS), and enable HTTPS. A backup on the same failed server is not sufficient disaster recovery.

## Restore
Example:
`gunzip -c backups/mtw_erp_YYYY-MM-DD_HH-MM-SS.sql.gz | docker compose exec -T db psql -U mtw_user -d mtw_erp`

## Important
This package is a deployable starter, not a finished statutory accounting product. Before production, add HTTPS, external off-site backups, password-change UI, MFA, full accounting double-entry, payroll/tax configuration, document attachments, email/WhatsApp integrations, and formal security review.
