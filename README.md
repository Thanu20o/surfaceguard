# Surfaceguard

Surfaceguard is a portfolio-sized external attack surface inventory and risk prioritization tool. It collects authorized-scope DNS data, queries public certificate transparency, makes bounded HTTPS/TLS observations, stores evidence, calculates explainable scores, and records changes between manual scans.

This is a local development project, not a production-ready security service. It has no authentication or tenant authorization; keep it bound to localhost. Read [known limitations](docs/limitations.md) before scanning. Only enter domains you are explicitly authorized to assess.

## What is implemented

- Organization creation with normalized root domains and strict hostname-boundary checks.
- DNS lookups for A, AAAA, CNAME, MX, NS, TXT, and CAA records.
- Passive CT hostname discovery through crt.sh, with clear warnings when unavailable.
- A public-address policy and pinned-IP HTTPS connection, TLS hostname verification, bounded response reads, request timeouts, and redirects that are never followed.
- TLS certificate metadata and HTTP response-header observations. Safe OpenAPI metadata checks on `api` hostnames; API operations are never invoked.
- SQLAlchemy persistence, PostgreSQL Compose configuration, SQLite local development, and an Alembic initial migration.
- Finding review/status updates, explainable asset risk factors, manual scan history, asset/DNS/HTTP/TLS changes, dashboard summaries, and CSV inventory export.
- Responsive React/TypeScript/Vite interface using real API data.
- Offline tests that mock external discovery and network assessment.

The incomplete items are listed in [docs/limitations.md](docs/limitations.md), including authentication, durable background workers, scheduled scans, PDF reports, ownership verification, comprehensive finding resolution, and complete change-history UI.

## Architecture and stack

- Frontend: React 19, TypeScript, Vite, Tailwind CSS, React Router, Axios, Recharts, Lucide.
- Backend: Python 3.11+, FastAPI, SQLAlchemy, Pydantic Settings, httpx, dnspython, Python SSL.
- Database: PostgreSQL 16 in Docker Compose. Local API development defaults to SQLite.
- Migrations: Alembic. Manual scans use FastAPI in-process background tasks; Redis/Celery scheduling is not implemented.

```text
frontend/src/       Pages, API client, types, styles
backend/app/api/    REST routers
backend/app/core/   Environment-backed configuration
backend/app/        SQLAlchemy models and database setup
backend/app/services/ Scope, discovery/assessment, and risk logic
backend/alembic/    Database migration environment
backend/tests/      Unit, API, and mocked scanner tests
docs/               Architecture, scoring, limitations
```

## Requirements

- Python 3.11 or newer.
- Node.js 20 or newer and npm, for the React development server.
- Docker Desktop with Compose, only if you want the PostgreSQL full-stack setup.

The backend can be run and tested without Docker or Node. The UI and Compose commands need those tools installed.

## Run everything with Docker Compose

Copy `.env.example` to `.env` and replace the local database password before use. The default is only a development placeholder.

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Linux/macOS:

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:5173`. The API documentation is at `http://localhost:8001/docs`. Services bind to localhost in Compose. Stop them with `Ctrl+C`; remove the containers with `docker compose down`. `docker compose down -v` also deletes the local database volume.

## Run the backend separately

From the repository root, in PowerShell:

```powershell
Set-Location backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8001
```

If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001` without activating; no machine execution-policy change is needed.

Linux/macOS:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8001
```

With no `DATABASE_URL`, the API uses `backend/surfaceguard.db` and creates its tables on startup for convenience. For PostgreSQL, set `DATABASE_URL` to a valid `postgresql+psycopg://...` connection and apply Alembic migrations.

## Run the frontend separately

Open a second terminal. The backend command above uses port 8001:

```powershell
Set-Location frontend
npm install
$env:VITE_API_URL = "http://127.0.0.1:8001/api"
npm run dev
```

Linux/macOS uses the same commands with `cd frontend`; set `VITE_API_URL=http://localhost:8001/api` before `npm run dev`. The frontend defaults to `http://localhost:8000/api` for a backend on its standard port.

## First workflow

1. Start the backend and frontend, then open the frontend.
2. Create an organization and enter its authorized root domain, such as a domain you control. IPs and URLs are rejected. This is an operator attestation; Surfaceguard does not verify ownership.
3. Open **Scans** and explicitly start a manual scan. The system does not scan on organization creation.
4. Review the scan status and warnings. A completed-with-warnings scan is distinct from a clean completion or a failure.
5. Review **Assets**, open an asset to inspect its DNS/TLS/HTTP observations, and review **Findings**. Finding status can be changed from its table.
6. Run another scan to compare DNS, HTTP, TLS, and asset-presence observations. The API exposes recorded changes at `/api/scans/{scan_id}/changes`.
7. Export the current inventory as CSV from **Reports**.

Assessment targets are limited to hostnames under the authorized root. Public DNS answers are required for network checks by default; localhost and private targets are rejected. Root DNS data can still be stored when a network check is skipped. A hostname label such as `dev` does not alone prove an environment is development or staging.

## API and data

Useful endpoints include:

- `POST /api/organizations`, `GET /api/organizations`
- `POST /api/organizations/{id}/scans`, `GET /api/organizations/{id}/scans`
- `GET /api/scans/{id}/changes`
- `GET /api/organizations/{id}/assets`, `GET /api/assets/{id}`
- `GET /api/organizations/{id}/findings`, `PATCH /api/findings/{id}`
- `GET /api/organizations/{id}/dashboard`
- `GET /api/organizations/{id}/reports/assets.csv`

FastAPI's interactive OpenAPI page is at `/docs`. Organizations define the root scope. Each hostname is unique per organization; each scan records DNS and assessment observations. Findings store concise evidence and remediation guidance. Scan-change rows store detected changes. No response page content is retained; an OpenAPI document body is read in memory only to extract a few metadata fields.

## Risk scoring

`technical severity × 0.40 + exposure × 0.25 + confidence × 0.20 + business impact × 0.15`. The current defaults are documented with limitations in [docs/risk-scoring.md](docs/risk-scoring.md). Finding severity is distinct from the asset score. A maximum finding severity is used instead of summing findings. Scores are illustrative prioritization, never a compromise probability.

## Tests

PowerShell and Linux/macOS, from `backend/`:

```powershell
python -m pytest -q
```

The scanner integration test mocks CT, DNS, HTTP, and TLS, so it needs no internet or real target. It uses `example.test`; it does not produce demo scan records in your database. Run API tests and unit tests with the same command.

## Troubleshooting

- **Frontend cannot reach API:** verify the backend is running at port 8001 and `VITE_API_URL` ends with `/api`. Check CORS `ALLOWED_ORIGINS` if you changed the frontend port.
- **Scan has warnings:** inspect the scan row's `error` field. Public CT may be unavailable, DNS providers may time out, or targets may have no public address.
- **No network observations:** private/loopback IPs are intentionally skipped by default; a missing DNS answer is not a successful assessment.
- **Postgres connection error:** wait for Compose's database health check; verify `.env` and recreate only the development container if configuration changed.
- **Migration issue:** run `python -m alembic current` and `python -m alembic upgrade head` from `backend/`.
- **PowerShell activation blocked:** use `.venv\Scripts\python.exe` explicitly rather than changing machine execution policy.

## Important files to understand first

1. `backend/app/services/scope.py` — domain normalization and exact hostname-boundary checks.
2. `backend/app/services/scanner.py` — passive discovery, bounded DNS/HTTPS assessment, and change detection.
3. `backend/app/services/risk.py` — weighted score and risk band.
4. `backend/app/models.py` — database entities and relationships.
5. `backend/app/api/` — REST endpoint behavior.
6. `frontend/src/api.ts` and `frontend/src/App.tsx` — client-server calls and primary screens.

For a class/interview demonstration, explain the authorized-scope rule first, create a workspace for a domain you control, start one manual scan, show raw observations beside findings, then explain why the asset score is a weighted prioritization score rather than exploit likelihood. A deterministic automated demo is provided through mocked tests, not fabricated dashboard seed data.