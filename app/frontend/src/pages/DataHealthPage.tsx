import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { DataHealthResponse, PipelineRunResponse } from "../api/types";
import { PipelineRunPanel } from "../components/PipelineRunPanel";
import { ErrorState, Skeleton } from "../components/States";
import { IconDatabase, IconPlay, IconRefresh } from "../components/icons";
import { formatCompact, formatDate, formatDateTime } from "../lib/format";
import { isRunTerminal } from "../lib/pipeline";

function StatusBadge({ status }: { status: string }) {
  const ok = status === "operational";
  return (
    <span className={`badge ${ok ? "badge--ok" : "badge--warn"}`}>
      <span className="badge__dot" />
      {ok ? "Operational" : status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <div className="metric__label">{label}</div>
      <div style={{ fontSize: "var(--fs-18)", fontWeight: 700, marginTop: "var(--sp-2)" }}>{value}</div>
    </div>
  );
}

export function DataHealthPage() {
  const [data, setData] = useState<DataHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pipelineRun, setPipelineRun] = useState<PipelineRunResponse | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [pipelinePanelOpen, setPipelinePanelOpen] = useState(false);
  const [pipelinePanelMode, setPipelinePanelMode] = useState<"preflight" | "run">("preflight");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.dataHealth());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load data health.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const triggerPipeline = async () => {
    setTriggering(true);
    setTriggerError(null);
    try {
      const next = await api.triggerPipeline();
      setPipelineRun(next);
      setPipelinePanelMode("run");
    } catch (err) {
      setTriggerError(err instanceof ApiError ? err.message : "Unable to start the pipeline run.");
    } finally {
      setTriggering(false);
    }
  };

  const openPipelinePanel = () => {
    setTriggerError(null);
    if (pipelineRun && !isRunTerminal(pipelineRun)) {
      setPipelinePanelMode("run");
    } else {
      setPipelinePanelMode("preflight");
    }
    setPipelinePanelOpen(true);
  };

  useEffect(() => {
    const runId = pipelineRun?.run_id;
    if (!runId || (pipelineRun && isRunTerminal(pipelineRun))) return;

    const timer = window.setInterval(async () => {
      try {
        const next = await api.pipelineRun(runId);
        setPipelineRun({ ...next, started_new: pipelineRun.started_new });
        if (next.result_state === "SUCCESS") await load();
      } catch (err) {
        setTriggerError(err instanceof ApiError ? err.message : "Unable to check pipeline run status.");
        window.clearInterval(timer);
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [pipelineRun, load]);

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Data Health</h1>
        <p>
          Freshness, coverage, and provenance for the City of Chicago datasets that power
          ChicagoPulse. All values are read live from the pipeline’s governed tables.
        </p>
      </div>

      {loading && (
        <div className="stack">
          <Skeleton height={90} radius={10} />
          <Skeleton height={220} radius={10} />
        </div>
      )}

      {!loading && error && (
        <div className="card card--pad">
          <ErrorState message={error} onRetry={load} />
        </div>
      )}

      {!loading && data && (
        <div className="stack">
          <div className="health-overview">
            <SummaryTile label="Last successful refresh" value={formatDateTime(data.last_refresh_at)} />
            <SummaryTile label="Latest reporting month" value={data.latest_reporting_month ?? "—"} />
            <div className="metric">
              <div className="metric__label">Pipeline status</div>
              <div style={{ marginTop: "var(--sp-3)" }}>
                <StatusBadge status={data.pipeline_status} />
              </div>
            </div>
            <div className="card card--pad health-controls">
              <div>
                <div className="metric__label">Pipeline controls</div>
                <div className="card__sub health-controls__description">
                  Run the Daily Refresh job on demand.
                </div>
              </div>
              <button
                className="btn btn--primary btn--sm"
                onClick={openPipelinePanel}
                disabled={triggering}
              >
                <IconPlay size={15} /> {pipelineRun && !isRunTerminal(pipelineRun) ? "View pipeline run" : "Run pipeline now"}
              </button>
            </div>
          </div>

          {pipelinePanelOpen && (
            <PipelineRunPanel
              mode={pipelinePanelMode}
              run={pipelineRun}
              starting={triggering}
              error={triggerError}
              onStart={triggerPipeline}
              onCancel={() => {
                setTriggerError(null);
                setPipelinePanelOpen(false);
              }}
              onCollapse={() => setPipelinePanelOpen(false)}
            />
          )}

          <div className="card">
            <div className="card--pad" style={{ paddingBottom: "var(--sp-3)" }}>
              <div className="card__head" style={{ marginBottom: 0 }}>
                <div className="card__title">
                  <span className="row" style={{ gap: 8 }}>
                    <IconDatabase size={18} /> Source datasets
                  </span>
                </div>
                <button className="btn btn--sm" onClick={load}>
                  <IconRefresh size={15} /> Refresh
                </button>
              </div>
              <p className="source-catalog__intro">
                Live sources are governed and available throughout ChicagoPulse. Potential future
                sources are official City datasets under consideration and are not currently ingested
                or available to Genie.
              </p>
            </div>
            <div className="table-wrap" style={{ border: "none", borderTop: "1px solid var(--border)" }}>
              <table className="data">
                <thead>
                  <tr>
                    <th scope="col">Dataset</th>
                    <th scope="col">Status</th>
                    <th scope="col">Category</th>
                    <th scope="col">Socrata ID</th>
                    <th scope="col" className="num">Rows</th>
                    <th scope="col">Coverage</th>
                    <th scope="col">Last ingested</th>
                  </tr>
                </thead>
                <tbody>
                  {data.datasets.map((d) => (
                    <tr key={d.dataset} className={d.usage_status === "in_use" ? "source-row--active" : "source-row--future"}>
                      <td>
                        {d.source_url ? (
                          <a href={d.source_url} target="_blank" rel="noreferrer">
                            {d.dataset}
                          </a>
                        ) : d.dataset}
                      </td>
                      <td>
                        <span className={`source-status source-status--${d.usage_status}`}>
                          {d.usage_status === "in_use" ? "In ChicagoPulse" : "Potential future source"}
                        </span>
                      </td>
                      <td>{d.category ?? "—"}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "var(--fs-12)" }}>
                        {d.source_url && d.socrata_id ? (
                          <a href={d.source_url} target="_blank" rel="noreferrer">
                            {d.socrata_id}
                          </a>
                        ) : d.socrata_id ?? "—"}
                      </td>
                      <td className="num tnum">{formatCompact(d.row_count)}</td>
                      <td>
                        {d.min_date ? `${formatDate(d.min_date)} – ${formatDate(d.max_date)}` : "—"}
                      </td>
                      <td>{d.last_ingested_at ? formatDateTime(d.last_ingested_at) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid--2" style={{ alignItems: "start" }}>
            <div className="card card--pad">
              <div className="card__title" style={{ marginBottom: "var(--sp-3)" }}>
                How ChicagoPulse calculates metrics
              </div>
              <p className="muted">{data.metric_explanation}</p>
            </div>
            <div className="card card--pad">
              <div className="card__title" style={{ marginBottom: "var(--sp-3)" }}>
                About the source data
              </div>
              <p className="muted">
                {data.source_notice}{" "}
                <a href="https://data.cityofchicago.org/" target="_blank" rel="noreferrer">
                  Visit the City of Chicago Data Portal
                </a>
                .
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
