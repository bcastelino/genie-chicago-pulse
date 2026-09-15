# AGENTS.md - ChicagoPulse

## Repository boundaries

- The Databricks App frontend and backend live in `app/`; make application
  changes there.
- The production data pipeline lives in `notebooks/` and governed Genie assets
  live in `genie/`. Do not modify either directory unless the user explicitly
  puts that surface in scope.
- `README.md` is a product flyer. Put installation, local running, validation,
  deployment, and troubleshooting instructions in `SETUP.md`.
- Preserve unrelated user changes. This checkout may not expose Git metadata.

## Current application state

- Public Appwrite Site: `https://chicagopulse.appwrite.network/`, backed by the
  restricted Appwrite Function proxy to the ChicagoPulse Databricks App.
- Routes: `/`, `/ask`, `/neighborhoods`, and `/data-health`.
- Ask includes live Genie metadata, multi-turn conversation links, chart/table/
  SQL/provenance views, suggested follow-ups, and answer feedback.
- Answer feedback uses the configured Genie Space and the app service principal.
  It stores no user identity in ChicagoPulse and does not automatically change
  Genie behavior.
- Neighborhood Pulse covers all 77 Community Areas with a local SVG choropleth,
  metrics, trends, and comparisons.
- Data Health derives end-to-end status from pipeline run-state and validation
  evidence, not `MAX(_ingested_at)`. It includes a confirmed, allowlisted Jobs
  API runner and real three-task state visualization.
- The Data Health source catalog marks four datasets `in_use` and four curated
  official datasets `future_scope`. Future sources are not ingested or exposed
  to Genie.
- The global shell uses centered desktop navigation, mobile bottom navigation,
  and a responsive footer.

## Non-negotiable implementation rules

- Namespace: `workspace.chicagopulse`.
- Data endpoints use allowlisted, parameterized templates in
  `app/server/data/queries.py`. Never add a general SQL endpoint.
- Genie normalization stays pure and unit-tested in
  `app/server/genie/normalize.py`.
- Resource selection remains server-side. The browser must never provide a
  Space ID, warehouse ID, job ID, notebook path, job parameters, or arbitrary
  run ID outside the bound job's verified runs.
- Public API models expose normalized fields only. Sanitize upstream errors and
  never return raw Databricks payloads, state messages, credentials, or secrets.
- Keep mock providers deterministic and production-safe. Production must refuse
  to start with `MOCK_MODE=true`.
- Preserve WCAG 2.2 AA, keyboard operation, visible focus, semantic live regions,
  reduced motion, responsive behavior, and the existing Chicago-at-dusk tokens.

## Bound Databricks resources

- Genie Space: `01f1a00325751a998b2eeb627266a3f2`, binding `genie-space`,
  permission `CAN_RUN`.
- SQL Warehouse: `ef7f63b5aa1f7b07`, binding `sql-warehouse`, permission
  `CAN_USE`.
- Daily Refresh Job: `990266492565902`, binding `daily-refresh-job`, permission
  `CAN_MANAGE_RUN`.
- CLI profile: `chicagopulse`.
- Production app URL:
  `https://chicagopulse-7474647819672339.aws.databricksapps.com`.

Re-check resource IDs and live deployment state before operational changes;
these values can drift.

## Verified commands

Windows PowerShell commands are shown below. Use the equivalent `.venv/bin/*`
paths on macOS or Linux.

Backend, from `app/`:

- Install: `.venv\Scripts\pip install -r requirements-dev.txt`
- Test: `.venv\Scripts\python -m pytest`
- Lint: `.venv\Scripts\ruff check server tests`
- Mock server: `$env:MOCK_MODE="true"; .venv\Scripts\uvicorn server.main:app --reload --port 8000`

Frontend, from `app/frontend/`:

- Install: `npm install`
- Typecheck: `npm run typecheck`
- Lint: `npm run lint`
- Test: `npm run test`
- Build: `npm run build`
- Dev server: `npm run dev`

Current validated baseline as of August 28, 2026: 47 backend tests and 30
frontend tests. Test counts are informational; re-run the suites instead of
assuming the counts remain fixed.

## Validation and deployment gate

Before deployment:

1. Run backend pytest and Ruff.
2. Run frontend typecheck, lint, Vitest, and the production build.
3. Run `databricks bundle validate -t prod -p chicagopulse`.

Deployment is an external production mutation and requires explicit user
approval. After approval, run from the repository root:

```powershell
databricks apps deploy -t prod -p chicagopulse --auto-approve
```

`databricks bundle deploy` uploads bundle resources but does not by itself
promote a Databricks App runtime snapshot. Prefer the Apps deployment command,
which performs the bundle work and starts the new snapshot.

After deployment, verify with:

```powershell
databricks apps get chicagopulse -p chicagopulse -o json
```

Require deployment `SUCCEEDED`, app `RUNNING`, and compute `ACTIVE`. Do not start
the Daily Refresh job unless the user separately authorizes a compute-affecting
pipeline run.

## Further contributor guidance

See `SETUP.md` for environment variables, local mock and authenticated modes,
the API map, troubleshooting, and the complete contributor workflow.
