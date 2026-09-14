# ChicagoPulse Setup and Operations

This guide is for contributors running, testing, or deploying ChicagoPulse. For
the product overview and live app, see [README.md](README.md). Review
[AGENTS.md](AGENTS.md) before changing application code.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer with npm
- Databricks CLI 1.x for authenticated development and deployment
- Access to the ChicagoPulse Databricks workspace and bound resources for live
  testing

The commands below use Windows PowerShell. On macOS or Linux, use
`.venv/bin/python`, `.venv/bin/pip`, and shell-style environment assignments.

## Repository layout

```text
app/
  app.yaml              Databricks Apps runtime and bound environment values
  requirements.txt      Python runtime dependencies
  requirements-dev.txt  Runtime plus pytest and Ruff
  server/               FastAPI API, providers, normalization, and mocks
  tests/                Backend tests
  frontend/             React, TypeScript, Vite, Vitest, and production dist
databricks.yml          App bundle and Databricks resource bindings
notebooks/              Governed data pipeline; outside normal app-edit scope
genie/                  Governed Genie assets and 30-question benchmark suite
.env.example            Local environment-variable template without secrets
```

## Install dependencies

From the repository root:

```powershell
python -m venv app/.venv
app/.venv/Scripts/python -m pip install --upgrade pip
app/.venv/Scripts/pip install -r app/requirements-dev.txt

Set-Location app/frontend
npm install
Set-Location ../..
```

Use `npm ci` instead of `npm install` when you want a clean install locked to
`package-lock.json`.

## Local configuration

The backend reads process environment variables and, when launched from `app/`,
an optional `app/.env` file.

```powershell
Copy-Item .env.example app/.env
```

Do not commit credentials or populated secret values.

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | `development` or `production` |
| `MOCK_MODE` | Uses deterministic fixtures when `true`; forbidden in production |
| `DATABRICKS_PROFILE` | Local CLI profile, normally `chicagopulse` |
| `DATABRICKS_HOST` | Optional local workspace host override |
| `GENIE_SPACE_ID` | Configured Genie Space |
| `DATABRICKS_WAREHOUSE_ID` | SQL Warehouse used by allowlisted queries |
| `DATABRICKS_JOB_ID` | Existing Daily Refresh job |
| `CATALOG` | Unity Catalog catalog, normally `workspace` |
| `SCHEMA_NAME` | Unity Catalog schema, normally `chicagopulse` |

## Run locally with mock data

Mock mode exercises chat polling, query results, the source catalog, and the
three-stage pipeline UI without calling Databricks or starting compute.

Start the API in one terminal:

```powershell
Set-Location app
$env:MOCK_MODE="true"
.venv/Scripts/uvicorn server.main:app --reload --host 127.0.0.1 --port 8000
```

Start Vite in another terminal:

```powershell
Set-Location app/frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api/*` to the FastAPI server on
port 8000. The header displays a **Demo data** badge.

## Run a production-style local build

This mode builds the SPA and serves the frontend and API from one FastAPI
process.

```powershell
Set-Location app/frontend
npm run build
Set-Location ..
$env:MOCK_MODE="true"
.venv/Scripts/uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Run locally against Databricks

Authenticate the CLI first:

```powershell
databricks auth login -p chicagopulse
```

Then launch the backend with mock mode disabled and the resource identifiers
kept server-side:

```powershell
Set-Location app
$env:ENVIRONMENT="development"
$env:MOCK_MODE="false"
$env:DATABRICKS_PROFILE="chicagopulse"
$env:GENIE_SPACE_ID="01f1a00325751a998b2eeb627266a3f2"
$env:DATABRICKS_WAREHOUSE_ID="ef7f63b5aa1f7b07"
$env:DATABRICKS_JOB_ID="990266492565902"
.venv/Scripts/uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Run Vite separately or build the SPA first. Live questions use the configured
Genie Space and may start SQL warehouse activity. The pipeline does not run
unless a user explicitly confirms **Start pipeline** in Data Health.

## API map

All browser calls are same-origin under `/api`.

| Method and path | Purpose |
| --- | --- |
| `GET /api/health` | Liveness and mock-mode flag |
| `GET /api/genie-agent` | Normalized configured Genie metadata and Space URL |
| `POST /api/conversations` | Start a Genie conversation |
| `POST /api/conversations/{id}/messages` | Send a follow-up question |
| `GET /api/conversations/{id}/messages/{mid}` | Poll a normalized Genie answer |
| `POST /api/conversations/{id}/messages/{mid}/feedback` | Submit, replace, or clear answer feedback |
| `GET /api/neighborhoods` | List Community Areas |
| `GET /api/neighborhoods/geo` | Community Area boundary GeoJSON |
| `GET /api/neighborhoods/map` | Latest completed-month map values |
| `GET /api/neighborhoods/{ca}/pulse` | Neighborhood metrics, trends, and categories |
| `GET /api/neighborhoods/compare?areas=...` | Compare up to four Community Areas |
| `GET /api/data-health` | Pipeline health, source coverage, and source catalog |
| `POST /api/data-health/pipeline-runs` | Start or reuse the bound refresh run |
| `GET /api/data-health/pipeline-runs/{run_id}` | Poll a verified bound-job run |

The frontend cannot send arbitrary SQL or select Databricks resources.

## Validation

Run the full application gate before deployment.

Backend, from `app/`:

```powershell
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check server tests
```

Frontend, from `app/frontend/`:

```powershell
npm run typecheck
npm run lint
npm run test
npm run build
```

Bundle validation, from the repository root:

```powershell
databricks bundle validate -t dev -p chicagopulse
databricks bundle validate -t prod -p chicagopulse
```

The validated baseline on August 28, 2026 is 47 backend tests and 30 frontend
tests. Re-run the suites because counts will change as coverage grows.

## Databricks resource bindings

`databricks.yml` binds the existing resources to the app service principal;
`app/app.yaml` exposes their values to FastAPI.

| Binding | Resource | Permission | Runtime value |
| --- | --- | --- | --- |
| `genie-space` | Genie Space `01f1a00325751a998b2eeb627266a3f2` | `CAN_RUN` | `GENIE_SPACE_ID` |
| `sql-warehouse` | Warehouse `ef7f63b5aa1f7b07` | `CAN_USE` | `DATABRICKS_WAREHOUSE_ID` |
| `daily-refresh-job` | Job `990266492565902` | `CAN_MANAGE_RUN` | `DATABRICKS_JOB_ID` |

The deployed app authenticates as its dedicated service principal. No personal
access token or resource secret belongs in frontend code, `.env.example`,
`app.yaml`, or `databricks.yml`.

## Deploy to Databricks Apps

Deployment changes external production state and requires explicit approval.
It does not authorize a Daily Refresh pipeline run.

After completing the validation gate, run from the repository root:

```powershell
databricks apps deploy -t prod -p chicagopulse --auto-approve
```

This command validates the project, uploads the bundle, creates a snapshot, and
starts the Databricks App. A standalone `databricks bundle deploy` does not by
itself promote the App runtime snapshot.

Verify the active deployment:

```powershell
databricks apps get chicagopulse -p chicagopulse -o json
```

Required terminal states:

- active deployment: `SUCCEEDED`
- app: `RUNNING`
- compute: `ACTIVE`

Live app:
[chicagopulse-7474647819672339.aws.databricksapps.com](https://chicagopulse-7474647819672339.aws.databricksapps.com)

## Genie feedback maintenance

ChicagoPulse forwards ratings and comments to the configured Genie Space as the
app service principal. It does not maintain a separate feedback database or add
user identity to feedback comments.

Once a month, and before a Genie configuration release:

1. Review feedback in Genie monitoring and group recurring concerns.
2. Verify proposed corrections against governed ChicagoPulse data.
3. Convert proven patterns into verified SQL or Agent instructions.
4. Run the existing 30-question benchmark before and after the change.
5. Accept the update only when answer quality improves without regressions.

Do not modify `genie/` as part of ordinary app work.

## Troubleshooting

### Vite or Vitest reports `Access is denied` on Windows

Windows sandboxing can prevent esbuild from traversing or loading
`vite.config.ts`. Run the same npm command in a normal local PowerShell session.
This is an environment restriction, not necessarily an application failure.

### FastAPI serves API responses but the UI is blank or returns 404

Build the SPA first:

```powershell
Set-Location app/frontend
npm run build
```

FastAPI serves `app/frontend/dist` only when that directory exists.

### Production refuses to start

Confirm `MOCK_MODE=false` and verify that all three bound resource IDs are
present. Production intentionally fails closed when mock mode is enabled or
required bindings are missing.

### Local Databricks calls return 401 or 403

Re-authenticate the `chicagopulse` profile and confirm that the current identity
can access the Genie Space, SQL Warehouse, and any operation being tested.

### Genie returns no result or a query error

Empty, failed, cancelled, and expired Genie messages are normalized application
states. Inspect the UI error, generated request details where available, and
backend logs without exposing raw upstream payloads to the browser.
