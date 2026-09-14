import { useEffect, useState } from "react";
import type { PipelineRunResponse, PipelineTaskResponse } from "../api/types";
import { formatDateTime } from "../lib/format";
import { isRunTerminal } from "../lib/pipeline";
import { IconCheck, IconExternalLink, IconPlay, IconPulse, IconX } from "./icons";

type StageState = "queued" | "running" | "succeeded" | "failed" | "skipped" | "cancelled";

const TERMINAL_STAGE_STATES = new Set(["TERMINATED", "SKIPPED", "INTERNAL_ERROR"]);

function stageState(task: PipelineTaskResponse): StageState {
  const lifeCycle = task.life_cycle_state.toUpperCase();
  const result = task.result_state?.toUpperCase();
  if (result === "SUCCESS") return "succeeded";
  if (result === "SKIPPED" || lifeCycle === "SKIPPED") return "skipped";
  if (result === "CANCELED" || result === "CANCELLED") return "cancelled";
  if (["RUNNING", "TERMINATING"].includes(lifeCycle)) return "running";
  if (["PENDING", "QUEUED", "BLOCKED", "WAITING_FOR_RETRY"].includes(lifeCycle)) return "queued";
  return result || TERMINAL_STAGE_STATES.has(lifeCycle) ? "failed" : "queued";
}

function stateLabel(state: StageState): string {
  return {
    queued: "Queued",
    running: "Running",
    succeeded: "Succeeded",
    failed: "Failed",
    skipped: "Skipped",
    cancelled: "Cancelled",
  }[state];
}

function formatDuration(durationMs: number | null | undefined): string {
  if (durationMs == null) return "—";
  const totalSeconds = Math.max(0, Math.floor(durationMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

function runStatus(run: PipelineRunResponse): { label: string; tone: StageState } {
  if (run.result_state === "SUCCESS") return { label: "Refresh succeeded", tone: "succeeded" };
  if (run.result_state === "SKIPPED") return { label: "Refresh skipped", tone: "skipped" };
  if (["CANCELED", "CANCELLED"].includes(run.result_state ?? "")) {
    return { label: "Refresh cancelled", tone: "cancelled" };
  }
  if (isRunTerminal(run)) return { label: "Refresh failed", tone: "failed" };
  if (run.life_cycle_state === "PENDING") return { label: "Refresh queued", tone: "queued" };
  return { label: "Refresh in progress", tone: "running" };
}

function StageIcon({ state }: { state: StageState }) {
  if (state === "succeeded") return <IconCheck size={18} />;
  if (["failed", "cancelled"].includes(state)) return <IconX size={18} />;
  if (state === "running") return <IconPulse size={18} />;
  return <span aria-hidden="true" />;
}

export function PipelineRunPanel({
  mode,
  run,
  starting,
  error,
  onStart,
  onCancel,
  onCollapse,
}: {
  mode: "preflight" | "run";
  run: PipelineRunResponse | null;
  starting: boolean;
  error: string | null;
  onStart: () => void;
  onCancel: () => void;
  onCollapse: () => void;
}) {
  const [, setClock] = useState(0);
  const terminal = Boolean(run && isRunTerminal(run));

  useEffect(() => {
    if (!run?.start_time || terminal) return;
    const timer = window.setInterval(() => setClock((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [run?.start_time, terminal]);

  const elapsedMs = (() => {
    if (!run) return null;
    if (run.duration_ms != null && terminal) return run.duration_ms;
    if (run.start_time) return Math.max(0, Date.now() - Date.parse(run.start_time));
    return run.duration_ms;
  })();

  if (mode === "preflight") {
    return (
      <section className="pipeline-panel pipeline-panel--preflight" aria-labelledby="pipeline-preflight-title">
        <div className="pipeline-panel__preflight-icon" aria-hidden="true"><IconPlay size={22} /></div>
        <div className="pipeline-panel__preflight-copy">
          <h2 id="pipeline-preflight-title">Start ChicagoPulse Daily Refresh?</h2>
          <p>
            This runs the existing production Databricks job and may consume compute. Only one
            refresh can run at a time.
          </p>
          {error && <p className="pipeline-panel__error" role="alert">{error}</p>}
        </div>
        <div className="pipeline-panel__actions">
          <button className="btn btn--primary" onClick={onStart} disabled={starting}>
            <IconPlay size={15} /> {starting ? "Starting…" : "Start pipeline"}
          </button>
          <button className="btn" onClick={onCancel} disabled={starting}>Cancel</button>
        </div>
      </section>
    );
  }

  if (!run) return null;
  const overall = runStatus(run);

  return (
    <section className="pipeline-panel" aria-labelledby="pipeline-run-title">
      <header className="pipeline-panel__header">
        <div>
          <div className={`pipeline-panel__status pipeline-panel__status--${overall.tone}`}>
            <span className="pipeline-panel__live-dot" /> {overall.label}
          </div>
          <h2 id="pipeline-run-title">ChicagoPulse Daily Refresh</h2>
        </div>
        <button className="btn btn--sm btn--ghost" onClick={onCollapse} aria-label="Collapse pipeline run">
          Collapse
        </button>
      </header>

      <ol className="pipeline-flow" aria-label="Pipeline stages">
        {run.tasks.map((task) => {
          const state = stageState(task);
          return (
            <li className="pipeline-stage" data-state={state} key={task.task_key}>
              <div className="pipeline-stage__node" aria-hidden="true"><StageIcon state={state} /></div>
              <div className="pipeline-stage__copy">
                <h3>{task.label}</h3>
                <span>{stateLabel(state)}</span>
                {task.duration_ms != null && <small>{formatDuration(task.duration_ms)}</small>}
              </div>
              <span className="visually-hidden">{task.label}: {stateLabel(state)}</span>
            </li>
          );
        })}
      </ol>

      <div className="pipeline-panel__footer">
        <dl className="pipeline-run-meta">
          <div><dt>Run</dt><dd className="tnum">{run.run_id}</dd></div>
          <div><dt>Started</dt><dd>{run.start_time ? formatDateTime(run.start_time) : "Waiting…"}</dd></div>
          <div><dt>{terminal ? "Duration" : "Elapsed"}</dt><dd className="tnum">{formatDuration(elapsedMs)}</dd></div>
          <div><dt>Source</dt><dd>{run.started_new ? "Started here" : "Existing active run"}</dd></div>
        </dl>
        {run.run_page_url && (
          <a className="btn btn--sm" href={run.run_page_url} target="_blank" rel="noreferrer">
            View run in Databricks <IconExternalLink size={14} />
          </a>
        )}
      </div>

      <div className="visually-hidden" role="status" aria-live="polite">
        {overall.label}. Run {run.run_id}.
      </div>
      {error && <p className="pipeline-panel__error" role="alert">{error}</p>}
    </section>
  );
}
