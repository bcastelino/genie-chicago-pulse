<div align="center">

# ChicagoPulse

**Ask Chicago a question. See the neighborhood evidence behind the answer.**

<p>
  <a href="https://chicagopulse.appwrite.network/"><img alt="Open the live ChicagoPulse Appwrite Site" src="https://img.shields.io/badge/Appwrite-Live_Site-FD366E?style=flat&amp;logo=appwrite&amp;logoColor=white"></a>
  <a href="https://chicagopulse-7474647819672339.aws.databricksapps.com"><img alt="Databricks Apps" src="https://img.shields.io/badge/Databricks-Apps-FF3621?style=flat&amp;logo=databricks&amp;logoColor=white"></a>
  <a href="https://www.databricks.com/product/ai-bi"><img alt="Databricks Genie" src="https://img.shields.io/badge/Databricks-Genie-1B3139?style=flat&amp;logo=databricks&amp;logoColor=white"></a>
  <a href="https://react.dev/"><img alt="React 18" src="https://img.shields.io/badge/React-18-20232A?style=flat&amp;logo=react&amp;logoColor=61DAFB"></a>
  <a href="https://www.typescriptlang.org/"><img alt="TypeScript 5" src="https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&amp;logo=typescript&amp;logoColor=white"></a>
  <a href="https://vite.dev/"><img alt="Vite 6" src="https://img.shields.io/badge/Vite-6-646CFF?style=flat&amp;logo=vite&amp;logoColor=white"></a>
  <a href="https://fastapi.tiangolo.com/"><img alt="FastAPI 0.115" src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&amp;logo=fastapi&amp;logoColor=white"></a>
  <a href="https://www.python.org/"><img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat&amp;logo=python&amp;logoColor=white"></a>
  <a href="https://bcastelino.com/blogs/blog/genie-app-wins-databricks-challenge/"><img alt="Read the ChicagoPulse writeup" src="https://img.shields.io/badge/Writeup-Read_the_story-C69214?style=flat&amp;logo=readme&amp;logoColor=white"></a>
</p>

![ChicagoPulse Thumbnail](public/chicagopulsehero.png)

ChicagoPulse turns governed City of Chicago open data into plain-language
answers, neighborhood comparisons, maps, and transparent operational health
signals. It is powered by Databricks Genie and built for residents, community
organizations, civic-data practitioners, and anyone who wants local context
without wrestling with raw datasets.

[**Open ChicagoPulse**](https://chicagopulse.appwrite.network/)

> The public experience runs on Appwrite Sites through a restricted Appwrite
> Function, backed by the ChicagoPulse Databricks App. The governed Databricks
> deployment remains a first-class target for authorized workspace users.

</div>

## ChicagoPulse wins Gold

ChicagoPulse earned **1st place in Track A: Real World Problem Solving** in the
**Databricks Genie-Powered App Challenge 2026**, finishing with 35.7 points and
earning selection for a BrickTalk spotlight.

[![ChicagoPulse wins Gold in the Databricks Genie-Powered App Challenge 2026](public/chicago-pulse-wins.png)](https://bcastelino.com/blogs/blog/genie-app-wins-databricks-challenge/)

[**Read the full ChicagoPulse challenge writeup**](https://bcastelino.com/blogs/blog/genie-app-wins-databricks-challenge/)

## One city, three ways to explore

### Ask ChicagoPulse

Ask natural-language questions about 311 service requests, business licenses,
building permits, and building violations. ChicagoPulse keeps the conversation
grounded in the configured Genie Space and lets you inspect:

- concise written answers and suggested follow-up questions;
- automatic charts with a table fallback;
- generated SQL and request provenance;
- the live Genie Agent identity and active conversation link; and
- answer feedback that maintainers can use to improve verified instructions and
  SQL examples.

### Neighborhood Pulse

Move from a citywide view to one of Chicago's 77 official Community Areas.
Search the city, select areas directly from the choropleth, compare up to four
neighborhoods, and explore:

- completed-month metrics with month-over-month context;
- 12-month 311 trends and top service-request types;
- business-license, permit, and violation activity; and
- explicit `N/A` states when a source is unavailable, never a misleading zero.

### Data Health

See why the data should be trusted before using it. Data Health separates
end-to-end pipeline success from source-ingestion freshness and includes:

- the last successful refresh and latest completed reporting month;
- coverage, row counts, ingestion timestamps, and official Socrata links;
- a source catalog that distinguishes datasets used by ChicagoPulse from
  potential future sources; and
- an inline, confirmed pipeline runner with real Databricks task states in the
  governed Databricks deployment. The public Appwrite view is intentionally
  read-only.

## The data behind ChicagoPulse

ChicagoPulse currently models four official City of Chicago datasets:

| In ChicagoPulse | City dataset |
| --- | --- |
| Service demand | [311 Service Requests](https://data.cityofchicago.org/d/v6vf-nfxy) |
| Business activity | [Business Licenses](https://data.cityofchicago.org/d/r5kz-chrr) |
| Development activity | [Building Permits](https://data.cityofchicago.org/d/ydr8-5enu) |
| Property conditions | [Building Violations](https://data.cityofchicago.org/d/22u3-xenr) |

The Data Health catalog also identifies official datasets being considered for
future scope, including food inspections, crimes, traffic crashes, and
affordable rental housing developments. These sources are clearly marked and
are not currently ingested or available to Genie.

## Built for verifiable answers

ChicagoPulse is designed to make evidence visible:

- Genie answers come from governed Unity Catalog Metric Views.
- Data queries use allowlisted, parameterized server-side templates. The browser
  cannot submit arbitrary SQL.
- Generated SQL, source IDs, and request provenance remain inspectable.
- Only fully completed calendar months appear in neighborhood metrics.
- Pipeline health comes from authoritative run-state and validation records,
  not merely the latest ingestion timestamp.
- Markdown is sanitized before rendering, API errors are normalized, and no
  resource credentials are exposed to the browser.

## How it works

```text
One GitHub repository
        |
        |-- Databricks Apps: app/
        |      React + FastAPI, same-origin /api/*
        |
        `-- Appwrite Sites: app/frontend/
               https://chicagopulse.appwrite.network/
                         |
                         v
               Appwrite Function gateway
               https://<function-id>.<region>.appwrite.run
                         |
                         | OAuth M2M
                         v
               ChicagoPulse Databricks App API
                         |
              Genie + SQL + Unity Catalog
```

Both targets use the same React components, routes, styles, and API models. The
Databricks deployment serves the compiled SPA and API together using its
dedicated service principal and explicit resource bindings. The Appwrite Site
uses a separate Function as a strict public gateway; Databricks credentials
never enter the browser bundle. An optional Appwrite edge domain can later give
the Function an `.appwrite.network` URL without requiring application changes.
Mock providers reproduce the core chat, data, and pipeline lifecycles for safe
local development.

## Project status

The public Appwrite Site is live at
[chicagopulse.appwrite.network](https://chicagopulse.appwrite.network/), backed
by the production snapshot on Databricks Apps Free Edition. The current
application includes the Chicago-at-dusk responsive interface, centered desktop
navigation, mobile bottom navigation, a global footer, answer feedback, the
task-level pipeline visualization, and the expanded Data Health source catalog.

## Contributing and running locally

Installation, environment variables, mock and authenticated local modes,
validation commands, deployment steps, and troubleshooting now live in
[SETUP.md](SETUP.md).

The data pipeline in `notebooks/` and Genie assets in `genie/` are maintained as
separate governed surfaces. Review [AGENTS.md](AGENTS.md) before making changes.

## Responsible use

ChicagoPulse summarizes public administrative data for neighborhood-level
exploration. It is not real-time, address-level, emergency, legal, or policy
decision support. Source records can be revised by the City of Chicago, so use
the linked datasets and Data Health evidence when decisions require additional
verification.
