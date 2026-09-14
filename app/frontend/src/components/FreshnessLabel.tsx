import { formatDateTime } from "../lib/format";

export function FreshnessLabel({
  label,
  value,
  isDate = true,
}: {
  label: string;
  value: string | null;
  isDate?: boolean;
}) {
  return (
    <span className="badge badge--muted" title={label}>
      <span className="badge__dot" style={{ background: "var(--ok)" }} />
      {label}: {value ? (isDate ? formatDateTime(value) : value) : "—"}
    </span>
  );
}
