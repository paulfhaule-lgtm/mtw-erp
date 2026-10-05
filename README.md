# MTW ERP — GitHub + Railway Production Package

MTW ERP is a Flask web ERP for Metal & Timber Works. This package is prepared for deployment from **GitHub to Railway** with a shared **PostgreSQL** database and persistent file storage for logo, stamp and uploaded documents.

## Included
- GitHub-ready source tree
- Railway Docker deployment (`Dockerfile` + `railway.toml`)
- Railway health check at `/health`
- Dynamic Railway `$PORT` support
- PostgreSQL via `DATABASE_URL`
- Persistent uploads directory: `/data/mtw_uploads`
- Secure session-cookie defaults for HTTPS
- Login for Accounts, Production, Store Keeper and MD
- MD-only Settings
- Company logo + stamp upload
- Material Requests with free-text materials
- Additional Material Requests per existing project
- Payment Requests and separate actual payments
- Partial payments and payment history
- Fundi/Staff loans with repayment history and balance
- Fundi register per project
- Fundi labour payments in installments until final payment
- Audit Trail
- Existing projects, inventory, invoices and workflow modules

## IMPORTANT: first public deployment
Before making the system public, set strong values in Railway Variables. Do not keep the sample passwords in production.

Required:
- `SECRET_KEY`
- `DATABASE_URL`

Recommended initial login passwords:
- `ACCOUNTS_PASSWORD`
- `PRODUCTION_PASSWORD`
- `STORE_PASSWORD`
- `MD_PASSWORD`

If those four variables are not set, the application currently falls back to the old demo passwords. **Set them before public use.** After login, each user can change their password from the profile/password page.

## 1. Put the package on GitHub
1. Extract this ZIP.
2. Create a new private GitHub repository, for example `mtw-erp`.
3. Upload the contents of this folder to the repository root.
4. Do **not** upload `.env`, passwords, database dumps or uploaded company documents.
5. Commit and push to the `main` branch.

The repository should have `Dockerfile`, `railway.toml`, `requirements.txt`, `app/`, and `.gitignore` at the root.

## 2. Create PostgreSQL on Railway
1. Open Railway and create a new project.
2. Add a PostgreSQL service.
3. Add a service from the GitHub repository for MTW ERP.
4. In the MTW ERP service Variables, create/link `DATABASE_URL` to the PostgreSQL service. Railway can expose the Postgres connection string as `DATABASE_URL`.
5. Add a strong `SECRET_KEY`.
6. Add the four role passwords listed above.

Example variable names:
```
SECRET_KEY=<long-random-secret>
DATABASE_URL=<Railway PostgreSQL connection string>
ACCOUNTS_PASSWORD=<strong-password>
PRODUCTION_PASSWORD=<strong-password>
STORE_PASSWORD=<strong-password>
MD_PASSWORD=<strong-password>
UPLOAD_DIR=/data/mtw_uploads
COOKIE_SECURE=1
MAX_UPLOAD_MB=16
```

Do not paste real passwords into GitHub or this README.

## 3. Add a Railway Volume for logo, stamp and documents
The application stores uploaded files under `/data/mtw_uploads`.

In the MTW ERP Railway service:
1. Add a **Volume**.
2. Mount it at:
```
/data
```
3. Keep `UPLOAD_DIR=/data/mtw_uploads`.

This makes the company logo, stamp and uploaded documents survive container redeploys. Without a persistent volume/object storage, uploaded files inside a container should not be treated as permanent production records.

## 4. Deploy
Railway will build the Dockerfile and run Gunicorn. The container automatically listens on Railway's `PORT` environment variable.

The health check is:
```
GET /health
```

A healthy response is JSON with `status: ok` and `database: connected`.

## 5. Generate the public URL
In Railway, open the MTW ERP service and generate a public domain under Networking/Domains.

Open that domain in a browser. You should see the MTW ERP login page.

## Initial logins
Use the passwords you set in Railway Variables:
- Username: `accounts`
- Username: `production`
- Username: `store`
- Username: `md`

The role permissions are handled by the application. MD has access to Settings.

## 6. Configure company identity
Login as `md` → **Settings**.

Enter:
- Company Name
- Phone
- Email
- TIN
- VRN
- Address
- Logo
- Company Stamp/Mhuri

The uploaded logo and stamp are stored under the persistent `/data` volume.

## 7. Shared ERP workflow
All four users connect to the same PostgreSQL database:

`Fundi/Staff → Production → Store Keeper/Accounts → MD approval → payment/issue → audit trail`

This means a material request created from one device can be seen by the authorized users from another device.

## 8. Local Docker test
For local testing:
1. Copy `.env.example` to `.env`.
2. Replace all sample secrets/passwords.
3. Run:
```
docker compose up -d --build
```
4. Open:
```
http://localhost
```

## Production security notes
- Keep the GitHub repository private unless there is a specific reason to make the source public.
- Never commit `.env`, database dumps, real passwords or company documents.
- Use a strong unique `SECRET_KEY`.
- Change all initial passwords immediately.
- Use Railway PostgreSQL as the shared database.
- Configure a persistent Railway Volume or object storage for uploads.
- Back up PostgreSQL regularly.
- Consider MFA/SSO and a formal security review before exposing the ERP to the wider internet.

## Database note
The current application creates missing tables automatically on startup. This is convenient for the initial Railway deployment. For future schema changes to an already-running production database, introduce a formal migration system (Alembic/Flask-Migrate) before changing model structures.
