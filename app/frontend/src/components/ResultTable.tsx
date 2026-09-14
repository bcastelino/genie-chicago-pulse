import type { Column } from "../api/types";
import { formatNumber } from "../lib/format";

function isNumeric(v: unknown): boolean {
  return typeof v === "number" || (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v)));
}

function renderCell(v: unknown, numeric: boolean): string {
  if (v === null || v === undefined || v === "") return "—";
  if (numeric && typeof v !== "boolean") {
    const n = Number(v);
    if (!Number.isNaN(n)) {
      const decimals = Number.isInteger(n) ? 0 : 2;
      return formatNumber(n, { decimals });
    }
  }
  return String(v);
}

export function ResultTable({
  columns,
  rows,
  caption,
}: {
  columns: Column[];
  rows: unknown[][];
  caption?: string;
}) {
  // A column is numeric if the majority of its non-empty cells are numeric.
  const numericCols = columns.map((_, ci) => {
    let num = 0;
    let total = 0;
    for (const row of rows) {
      const v = row[ci];
      if (v === null || v === undefined || v === "") continue;
      total++;
      if (isNumeric(v)) num++;
    }
    return total > 0 && num / total >= 0.6;
  });

  return (
    <div className="table-wrap" role="region" aria-label={caption ?? "Result table"} tabIndex={0}>
      <table className="data">
        {caption && <caption className="visually-hidden">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c, ci) => (
              <th key={c.name + ci} scope="col" className={numericCols[ci] ? "num" : undefined}>
                {c.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {columns.map((_, ci) => (
                <td key={ci} className={numericCols[ci] ? "num tnum" : undefined}>
                  {renderCell(row[ci], numericCols[ci])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
