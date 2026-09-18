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
- An Appwrite Cloud project for the optional public Site and Function deployment

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
appwrite/
  functions/
    databricks-proxy/   Restricted public gateway with isolated dependencies
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

The optional Appwrite Function has its own environment and dependencies:

```powershell
python -m venv appwrite/functions/databricks-proxy/.venv
appwrite/functions/databricks-proxy/.venv/Scripts/pip install -r appwrite/functions/databricks-proxy/requirements-dev.txt
```

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

No Appwrite variables are required for this workflow. With no frontend
configuration, `VITE_DEPLOYMENT_TARGET` defaults to `databricks` and API calls
remain relative to the current origin.

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

Databricks and local browser calls are same-origin under `/api`. An Appwrite
build sends the same paths to its configured Function URL.

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

The public Appwrite gateway exposes the read-only and Genie interaction routes
listed above through answer feedback, plus `GET /api/data-health`. It blocks
`POST /api/data-health/pipeline-runs` with `403` and does not expose
`GET /api/data-health/pipeline-runs/{run_id}`. Unknown paths and unsupported
methods are not forwarded to Databricks.

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

Appwrite Function, from `appwrite/functions/databricks-proxy/`:

```powershell
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check src tests
```

To verify both frontend targets, build Appwrite first with a non-production URL,
then finish with the default Databricks build so `dist/` remains same-origin:

```powershell
Set-Location app/frontend
$env:VITE_DEPLOYMENT_TARGET="appwrite"
$env:VITE_API_BASE_URL="https://example.invalid"
npm run build
Remove-Item Env:VITE_DEPLOYMENT_TARGET
Remove-Item Env:VITE_API_BASE_URL
npm run build
Set-Location ../..
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

Databricks live app:
[chicagopulse-7474647819672339.aws.databricksapps.com](https://chicagopulse-7474647819672339.aws.databricksapps.com)

### Deploy from Git

For a Databricks App deployment sourced directly from this repository, use:

| Setting | Value |
| --- | --- |
| Git reference | `main` |
| Reference type | Branch |
| Source code path | `app` |

The `app/package.json` file is a build wrapper for this source root. Its build
script performs a clean install from `app/frontend/package-lock.json`, includes
the Vite and TypeScript development dependencies, and generates
`app/frontend/dist` before FastAPI starts. The frontend package and dependency
definitions remain under `app/frontend/`.

## Deploy with Appwrite Sites and Functions

This mode publishes the existing React frontend as a static Site and sends API
calls through a separate Python Function to the existing Databricks App. It does
not copy the React application or move ChicagoPulse business logic into
Appwrite.

### Frontend runtime variables

Only these values belong in the Appwrite Site build:

| Variable | Production value |
| --- | --- |
| `VITE_DEPLOYMENT_TARGET` | `appwrite` |
| `VITE_API_BASE_URL` | `https://<function-id>.<region>.appwrite.run` |

Vite embeds these variables into the static browser bundle. Never configure a
Databricks host, client ID, client secret, or access token on the Site. The
initial API base should be the Function's generated regional `.appwrite.run`
domain. If an optional `.appwrite.network` edge domain is later added to the
Function, update the API base and rebuild the Site.

### Function variables

Configure these only on the Appwrite Function:

| Variable | Purpose |
| --- | --- |
| `DATABRICKS_HOST` | HTTPS workspace URL used for OAuth M2M |
| `DATABRICKS_CLIENT_ID` | External gateway service-principal client ID |
| `DATABRICKS_CLIENT_SECRET` | OAuth secret; mark this variable **Secret** |
| `DATABRICKS_APP_URL` | HTTPS ChicagoPulse `.databricksapps.com` base URL |
| `DATABRICKS_WAKE_CLIENT_ID` | Dedicated wake service-principal client ID |
| `DATABRICKS_WAKE_CLIENT_SECRET` | Dedicated wake OAuth secret; mark this variable **Secret** |
| `DATABRICKS_APP_NAME` | Fixed wake target; must be `chicagopulse` |
| `ALLOWED_ORIGINS` | Comma-separated exact Site and explicit localhost origins |
| `UPSTREAM_TIMEOUT_SECONDS` | Optional, defaults to and recommends `20`; valid range 1–25 |

The Function rejects unsafe base URLs and origins. Values above 20 seconds
should be used carefully because synchronous Function-domain requests have a
30-second execution window and still need time for OAuth and response handling.
Function variable changes require a Function redeployment; Site variable
changes require a Site rebuild and deployment.

The three wake variables belong only in the Appwrite Function environment.
Never place them, a Databricks host, or any Databricks credential in a `VITE_*`
variable because Vite embeds those values in the public browser bundle.

### Databricks service principal

Create or select a normal gateway Databricks service principal, assign it to the
ChicagoPulse workspace, create an OAuth secret, and keep it at only `CAN USE` on
the ChicagoPulse App. It does not need direct Genie, SQL Warehouse, Jobs, or
Unity Catalog permissions. Those operations continue inside ChicagoPulse under
the Databricks App's dedicated service principal and existing resource bindings.

Use a second, dedicated wake service principal for
`DATABRICKS_WAKE_CLIENT_ID` and `DATABRICKS_WAKE_CLIENT_SECRET`. Grant it only
the minimum Databricks App management permission necessary to inspect and start
the single ChicagoPulse App. Do not upgrade or reuse the normal gateway
identity, and do not grant broader workspace, SQL, Genie, Jobs, or Unity Catalog
access. Permission and service-principal creation are manual cloud operations;
the repository does not perform them.

The Function creates one OAuth M2M `WorkspaceClient` and asks the SDK for a
current authentication header for every outgoing request. It never stores an
access token in frontend code or forwards a browser-supplied authorization
header. Follow Databricks' official [external App API authentication](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/connect-local)
and [App permissions](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/permissions)
guidance when creating this identity and grant.

The Appwrite-only `POST /api/runtime/wake` route uses the dedicated wake
identity and the fixed `DATABRICKS_APP_NAME`; it does not forward the request to
FastAPI and accepts no caller-supplied app name or workspace URL. If the App is
already active it returns `ready`; otherwise it requests a start and returns
`starting`. A 60-second in-process cooldown reduces duplicate starts from the
same warm Function instance. The cooldown is best-effort because Appwrite may
run multiple Function instances, so platform rate limiting remains important.

After an explicit user click, the Appwrite Site polls health for at most about
90 seconds and retries the original live-data request when the App is ready.
The Databricks-hosted frontend never exposes this control, and opening the
static homepage never issues a wake request. Free Edition can still refuse a
start when compute or fair-usage limits are exhausted; this recovery flow does
not make Free Edition an SLA-backed always-on service.

### Appwrite Function settings

| Setting | Value |
| --- | --- |
| Repository / branch | `bcastelino/genie-chicago-pulse` / `main` |
| Root directory | `appwrite/functions/databricks-proxy` |
| Runtime | Python 3.12 |
| Install command | `pip install -r requirements.txt` |
| Entrypoint | `main.py` |
| Execute access | `Any` |
| Appwrite API scopes | None |
| Git path filter | `appwrite/functions/databricks-proxy/**` |

The generated Function domain normally looks like
`https://<function-id>.<region>.appwrite.run`.

### Appwrite Site settings

| Setting | Value |
| --- | --- |
| Repository / branch | `bcastelino/genie-chicago-pulse` / `main` |
| Root directory | `app/frontend` |
| Framework | React / Vite, static Site |
| Install command | `npm install` |
| Build command | `npm run build` |
| Output directory | `./dist` |
| SPA fallback | `index.html` |
| Git path filter | `app/frontend/**` |
| Production URL | `https://chicagopulse.appwrite.network/` |

The public Site is
[chicagopulse.appwrite.network](https://chicagopulse.appwrite.network/). Configure
its exact origin, `https://chicagopulse.appwrite.network`, in
`ALLOWED_ORIGINS`. Preview deployments do not receive API access automatically;
add a preview's exact origin and redeploy the Function when one needs access.

### Security boundary

CORS is not authentication. The exact `ALLOWED_ORIGINS` list stops unauthorized
browser origins, but curl, scripts, and bots can call a public Function without
an `Origin` header. The explicit route allowlist, blocked administrative routes,
Appwrite Firewall, and rate limiting are therefore the actual protection for
public resource consumption. Configure platform-level rate limits before broad
public promotion and monitor Function executions for unusual volume.

### Manual deployment order

Deployment changes external state and is not part of repository validation.

1. Create the Appwrite Site and Function resources from the roots above.
2. Create the normal gateway identity with only `CAN USE`, plus a separate wake
   identity with the minimum App start permission for ChicagoPulse.
3. Set the Function-only variables, including the separate wake identity, fixed
   `DATABRICKS_APP_NAME=chicagopulse`, and exact Site origin, then deploy the
   Function.
4. Set the Site's two `VITE_*` variables using the generated `.appwrite.run`
   Function URL, then deploy the Site.
5. Verify `GET /api/health`, Ask, neighborhoods, Data Health, `/`, and SPA deep
   links from the deployed Site.
6. Verify an allowed-origin wake preflight returns `204`, a rejected origin
   returns `403` without an allow-origin header, the pipeline trigger returns
   `403`, and the pipeline run-status path returns `404`.
7. Confirm the browser console is free of request and CORS errors and Function
   logs contain no credentials, tokens, request bodies, or configured URLs.

Appwrite supports monorepo root directories and Git path filters for both
resources. See the official [React Site guide](https://appwrite.io/docs/products/sites/quick-start/react),
[Function Git deployment guide](https://appwrite.io/docs/products/functions/deploy-from-git),
[Function variable guide](https://appwrite.io/docs/products/functions/environment-variables),
and [Function execution guide](https://appwrite.io/docs/products/functions/execute).

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
