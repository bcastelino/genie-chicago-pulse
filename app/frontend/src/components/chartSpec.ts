// Chart-type heuristic, kept dependency-free so it stays in the main bundle
// while the heavy Recharts renderer is lazy-loaded on demand.
import type { Column } from "../api/types";

export type ChartSpec =
  | { kind: "line"; xKey: string; series: string[]; xIsMonth: boolean }
  | { kind: "bar"; xKey: string; series: string[]; horizontal: boolean; xIsMonth: boolean }
  | { kind: "none" };

const DATE_RE = /^\d{4}-\d{2}(-\d{2})?/;

function classify(columns: Column[], rows: unknown[][]) {
  const numeric: boolean[] = [];
  const dateLike: boolean[] = [];
  columns.forEach((c, ci) => {
    let num = 0;
    let date = 0;
    let total = 0;
    for (const row of rows) {
      const v = row[ci];
      if (v === null || v === undefined || v === "") continue;
      total++;
      if (typeof v === "number" || (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v)))) {
        num++;
      }
      if (typeof v === "string" && DATE_RE.test(v)) date++;
    }
    const nameHints = /month|date|period/i.test(c.name);
    numeric[ci] = total > 0 && num / total >= 0.6 && !(nameHints && date / total >= 0.6);
    dateLike[ci] = total > 0 && (date / total >= 0.6 || (nameHints && date / total > 0));
  });
  return { numeric, dateLike };
}

/** Choose an appropriate chart, or "none" to fall back to a table. */
export function chooseChart(columns: Column[], rows: unknown[][]): ChartSpec {
  if (!rows.length || columns.length < 2) return { kind: "none" };
  const { numeric, dateLike } = classify(columns, rows);

  const dateIdx = dateLike.findIndex(Boolean);
  const numericIdx = numeric.map((n, i) => (n ? i : -1)).filter((i) => i >= 0);
  const categoricalIdx = columns.map((_, i) => i).filter((i) => !numeric[i] && !dateLike[i]);

  if (dateIdx >= 0 && numericIdx.length >= 1) {
    return {
      kind: "line",
      xKey: columns[dateIdx].name,
      series: numericIdx.slice(0, 4).map((i) => columns[i].name),
      xIsMonth: true,
    };
  }

  if (categoricalIdx.length === 1 && numericIdx.length >= 1) {
    const single = numericIdx.length === 1;
    return {
      kind: "bar",
      xKey: columns[categoricalIdx[0]].name,
      series: numericIdx.slice(0, 4).map((i) => columns[i].name),
      horizontal: single,
      xIsMonth: false,
    };
  }

  return { kind: "none" };
}
