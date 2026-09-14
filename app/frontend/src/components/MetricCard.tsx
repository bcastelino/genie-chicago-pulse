import { formatNumber, formatPercent } from "../lib/format";

export function Delta({
  pct,
  higherIsBetter,
}: {
  pct: number | null;
  higherIsBetter?: boolean;
}) {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return null;
  const arrow = pct > 0 ? "\u25B2" : pct < 0 ? "\u25BC" : "\u2013";
  let cls = "delta--flat";
  if (pct !== 0 && higherIsBetter !== undefined) {
    const good = pct > 0 === higherIsBetter;
    cls = good ? "delta--good" : "delta--bad";
  }
  return (
    <span className={`delta ${cls}`} title="Change vs. previous completed month">
      <span aria-hidden="true">{arrow}</span>
      <span className="tnum">{formatPercent(pct)}</span>
      <span className="visually-hidden">
        {pct > 0 ? "increase" : pct < 0 ? "decrease" : "no change"} versus previous month
      </span>
    </span>
  );
}

export function MetricCard({
  label,
  value,
  unit,
  decimals = 0,
  momPct,
  higherIsBetter,
  available = true,
  footNote,
}: {
  label: string;
  value: number | null;
  unit?: string | null;
  decimals?: number;
  momPct?: number | null;
  higherIsBetter?: boolean;
  available?: boolean;
  footNote?: string;
}) {
  const showValue = available && value !== null && value !== undefined;
  return (
    <div className={`metric ${available ? "" : "metric--na"}`}>
      <div className="metric__label">{label}</div>
      {showValue ? (
        <div className="metric__value tnum">
          {formatNumber(value, { decimals })}
          {unit && unit !== "count" && <span className="metric__unit">{unit}</span>}
        </div>
      ) : (
        <div className="metric__na" title="No data available for this dataset and month">
          N/A
        </div>
      )}
      <div className="metric__foot">
        {showValue && momPct !== undefined ? (
          <Delta pct={momPct ?? null} higherIsBetter={higherIsBetter} />
        ) : null}
        {footNote && <span>{footNote}</span>}
        {!available && <span>Not reported for this month</span>}
      </div>
    </div>
  );
}
