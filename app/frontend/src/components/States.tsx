import type { ReactNode } from "react";
import { IconAlert, IconInbox } from "./icons";

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="state state--inline" role="status">
      <IconInbox className="state__icon" size={40} />
      <div className="state__title">{title}</div>
      {message && <p>{message}</p>}
      {action}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="state state--error state--inline" role="alert">
      <IconAlert className="state__icon" size={40} />
      <div className="state__title">{title}</div>
      {message && <p>{message}</p>}
      {onRetry && (
        <button className="btn btn--sm" onClick={onRetry}>
          Try Again
        </button>
      )}
    </div>
  );
}

export function Skeleton({
  width = "100%",
  height = 16,
  radius,
}: {
  width?: string | number;
  height?: string | number;
  radius?: number;
}) {
  return (
    <span
      className="skeleton"
      style={{
        display: "block",
        width,
        height,
        borderRadius: radius,
      }}
    />
  );
}

export function ProgressBar({ label }: { label?: string }) {
  return (
    <div role="status" aria-live="polite">
      {label && (
        <div className="muted" style={{ fontSize: "var(--fs-13)", marginBottom: 6 }}>
          {label}
        </div>
      )}
      <div className="progress">
        <div className="progress__bar" />
      </div>
    </div>
  );
}
