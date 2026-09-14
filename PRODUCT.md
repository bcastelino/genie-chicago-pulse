# ChicagoPulse Product Definition

## Register

`product`

The homepage is the expressive brand surface. Ask, Neighborhood Pulse, and Data
Health are working product surfaces where clarity, confidence, accessibility,
and efficient exploration take priority.

## Product purpose

ChicagoPulse turns governed City of Chicago open data into plain-language
answers, neighborhood comparisons, maps, and transparent operational health
signals. Success means people can ask useful local questions, understand what
changed, inspect the evidence, and determine whether the underlying data is
current enough for their purpose.

## Primary users

- Chicago residents seeking understandable neighborhood context.
- Neighborhood organizations and community groups comparing local conditions.
- Civic-data practitioners who need a fast, transparent exploration layer.
- Maintainers who operate the Genie Agent, governed metrics, and refresh job.

## Core user journeys

### Ask ChicagoPulse

Users ask about 311 requests, business licenses, building permits, and building
violations in natural language. A productive answer provides readable context,
an appropriate chart or table, generated SQL, source and request provenance,
follow-up questions, and an optional path into the live Genie conversation.

Completed answers support positive or negative feedback. A negative rating
collects a structured reason and optional comment. Feedback is submitted as the
app service principal to the configured Genie Space; it does not automatically
retrain or alter the Agent.

### Explore neighborhoods

Users search or select any of Chicago's 77 official Community Areas, inspect
completed-month metrics and trends, and compare up to four areas. Missing source
coverage is represented as unavailable rather than zero.

### Verify data health

Users inspect the last successful end-to-end refresh, reporting period, source
coverage, row counts, ingestion freshness, and official City dataset links.
Datasets used by ChicagoPulse are visually distinct from curated potential
future sources, which are not ingested or exposed to Genie.

Maintainers can open a preflight panel and explicitly start the single bound
ChicagoPulse Daily Refresh job. The live panel reflects real Jobs API task
states for ingestion, transformation, and validation. It never fabricates
progress or statistics.

## Current data scope

ChicagoPulse currently uses:

- 311 Service Requests (`v6vf-nfxy`)
- Business Licenses (`r5kz-chrr`)
- Building Permits (`ydr8-5enu`)
- Building Violations (`22u3-xenr`)

The Data Health catalog currently marks Food Inspections, Crimes, Traffic
Crashes, and Affordable Rental Housing Developments as potential future sources.
This is discovery context, not a delivery commitment.

## Trust and governance model

- Genie operates over governed Unity Catalog Metric Views.
- Server data endpoints use allowlisted, parameterized query templates; there is
  no general-purpose SQL endpoint.
- The browser cannot select a Genie Space, warehouse, refresh job, job
  parameters, or arbitrary run.
- Pipeline success is derived from terminal run-state and validation evidence.
  Ingestion timestamps remain a separate source-freshness signal.
- Only fully completed calendar months are reported in neighborhood metrics.
- Generated Markdown is sanitized, public API models are normalized, and raw
  Databricks errors or secrets are never returned to the browser.
- The deployed Databricks App uses its dedicated service principal and explicit
  resource bindings.

## Out of scope

- Real-time, emergency, address-level, legal, or policy decision support.
- Anonymous public access outside Databricks account permissions.
- Arbitrary user-authored SQL or user-selected compute resources.
- Automatic changes to Genie based on answer feedback.
- Per-dataset pipeline telemetry beyond the verified task-level workflow.
- Ingestion or modeling of datasets labeled as potential future sources.

## Brand personality

Trustworthy, grounded, and energetic. ChicagoPulse should communicate civic
credibility without becoming institutional, bureaucratic, or dull.

## Design principles

- Make Chicago recognizable without presenting expressive graphics as precise
  geographic evidence.
- Put evidence close to claims so civic credibility is visible.
- Keep the homepage energetic and working routes calm and legible.
- Use progressive disclosure so users can begin with a question and inspect
  technical detail only when needed.
- Preserve local specificity in language, geography, and provenance.
- Use the Chicago-at-dusk tokens, typography, spacing, button vocabulary, and
  restrained motion consistently.
- Keep desktop navigation centered, mobile navigation thumb-accessible, and the
  global footer clear of fixed mobile controls.

## Accessibility and inclusion

WCAG 2.2 AA is non-negotiable. The product must provide full keyboard access,
visible focus, semantic controls and ordered workflow stages, live-region
announcements, color-safe differentiation, accessible contrast, responsive
layouts without horizontal page overflow, and reduced-motion alternatives.

## Quality signals

- Users can complete all three primary journeys without understanding
  Databricks, Socrata, SQL, or pipeline terminology.
- Every answer can be traced to its generated SQL and request provenance.
- Operational status never implies success from ingestion time alone.
- Future data sources cannot be mistaken for live ChicagoPulse coverage.
- Changes pass backend tests and Ruff, frontend typecheck, lint, Vitest, and the
  production build before bundle validation or deployment.
