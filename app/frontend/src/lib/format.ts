const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function formatNumber(value: number | null | undefined, opts?: { decimals?: number }): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const decimals = opts?.decimals ?? 0;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString(undefined, {
      notation: "compact",
      maximumFractionDigits: 1,
    });
  }
  return formatNumber(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

/** Turn a 'YYYY-MM' or ISO date into 'Month YYYY'. */
export function monthLabel(value: string | null | undefined): string {
  if (!value) return "—";
  const key = value.slice(0, 7);
  const [year, month] = key.split("-");
  const idx = Number(month) - 1;
  if (idx >= 0 && idx < 12 && year) return `${MONTHS[idx]} ${year}`;
  return value;
}

/** Short month for chart axes: 'Jun ’24'. */
export function monthShort(value: string | null | undefined): string {
  if (!value) return "";
  const key = value.slice(0, 7);
  const [year, month] = key.split("-");
  const idx = Number(month) - 1;
  if (idx >= 0 && idx < 12 && year) {
    return `${MONTHS[idx].slice(0, 3)} \u2019${year.slice(2)}`;
  }
  return value;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
