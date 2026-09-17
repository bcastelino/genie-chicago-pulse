import type { ApiError } from "../api/client";
import {
  isWakeableServiceError,
  useLiveServiceRecovery,
} from "../hooks/useLiveServiceRecovery";
import { IconAlert, IconCheck, IconRefresh } from "./icons";
import { ErrorState, ProgressBar } from "./States";

export function LiveServiceErrorState({
  error,
  onRetry,
}: {
  error: ApiError;
  onRetry: () => void | Promise<void>;
}) {
  if (!isWakeableServiceError(error)) {
    return <ErrorState message={error.message} onRetry={() => void onRetry()} />;
  }
  return <AppwriteServiceRecoveryState error={error} onRetry={onRetry} />;
}

function AppwriteServiceRecoveryState({
  error,
  onRetry,
}: {
  error: ApiError;
  onRetry: () => void | Promise<void>;
}) {
  const { phase, start } = useLiveServiceRecovery(error, onRetry);
  const starting = phase === "starting";
  const failed = phase === "failed";
  const ready = phase === "ready";
  const title = failed
    ? "Live services could not be started"
    : ready
      ? "Live services are ready."
      : starting
        ? "Starting ChicagoPulse live services…"
        : "Live ChicagoPulse services are unavailable";
  const message = failed
    ? "ChicagoPulse could not start its live data service right now. Free Edition usage limits or a temporary Databricks issue may prevent startup."
    : ready
      ? "Reconnecting to the live data service now."
      : starting
        ? "Databricks Free Edition may take a moment to resume. ChicagoPulse will reconnect automatically when the service is ready."
        : "The Databricks service that powers live ChicagoPulse data is currently stopped or unavailable.";
  const Icon = ready ? IconCheck : starting ? IconRefresh : IconAlert;

  return (
    <div
      className={`state state--inline state--service state--service-${phase}`}
      role={failed || phase === "unavailable" ? "alert" : "status"}
      aria-live={failed || phase === "unavailable" ? "assertive" : "polite"}
      aria-busy={starting}
    >
      <Icon className="state__icon" size={40} aria-hidden="true" />
      <div className="state__title">{title}</div>
      <p>{message}</p>
      {starting && (
        <div className="state__progress">
          <ProgressBar label="Waiting for live services" />
        </div>
      )}
      {!ready && (
        <div className="state__actions">
          <button
            className="btn btn--primary"
            type="button"
            onClick={() => void start()}
            disabled={starting}
          >
            <IconRefresh size={15} aria-hidden="true" />
            {starting ? "Starting live service…" : "Start live service"}
          </button>
          {!starting && (
            <button className="btn btn--ghost" type="button" onClick={() => void onRetry()}>
              Retry connection
            </button>
          )}
        </div>
      )}
    </div>
  );
}
