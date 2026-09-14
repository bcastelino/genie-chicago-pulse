import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Column } from "../api/types";
import { AXIS_COLOR, CHART_COLORS, GRID_COLOR } from "../design/theme";
import { formatCompact, formatNumber, monthShort } from "../lib/format";
import type { ChartSpec } from "./chartSpec";

export type { ChartSpec } from "./chartSpec";
export { chooseChart } from "./chartSpec";

function toObjects(columns: Column[], rows: unknown[][]): Record<string, unknown>[] {
  const names = columns.map((c) => c.name);
  return rows.map((row) => {
    const obj: Record<string, unknown> = {};
    names.forEach((n, i) => {
      const v = row[i];
      obj[n] = typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v)) ? Number(v) : v;
    });
    return obj;
  });
}

const axisTick = { fill: AXIS_COLOR, fontSize: 12 };

export function AutoChart({
  columns,
  rows,
  spec,
}: {
  columns: Column[];
  rows: unknown[][];
  spec: ChartSpec;
}) {
  if (spec.kind === "none") return null;
  const data = toObjects(columns, rows);
  const tooltipFormatter = (v: number | string) =>
    typeof v === "number" ? formatNumber(v, { decimals: Number.isInteger(v) ? 0 : 2 }) : String(v);

  if (spec.kind === "line") {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID_COLOR} vertical={false} />
          <XAxis
            dataKey={spec.xKey}
            tick={axisTick}
            tickFormatter={spec.xIsMonth ? (v) => monthShort(String(v)) : undefined}
            tickLine={false}
            axisLine={{ stroke: GRID_COLOR }}
          />
          <YAxis tick={axisTick} tickFormatter={(v) => formatCompact(Number(v))} tickLine={false} axisLine={false} width={48} />
          <Tooltip formatter={tooltipFormatter} labelFormatter={spec.xIsMonth ? (l) => monthShort(String(l)) : undefined} />
          {spec.series.length > 1 && <Legend />}
          {spec.series.map((s, i) => (
            <Line
              key={s}
              type="monotone"
              dataKey={s}
              stroke={CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2.25}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  const height = spec.horizontal ? Math.max(240, data.length * 34 + 40) : 320;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={spec.horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 20, bottom: 4, left: 4 }}
      >
        <CartesianGrid stroke={GRID_COLOR} horizontal={!spec.horizontal} vertical={spec.horizontal} />
        {spec.horizontal ? (
          <>
            <XAxis type="number" tick={axisTick} tickFormatter={(v) => formatCompact(Number(v))} tickLine={false} axisLine={{ stroke: GRID_COLOR }} />
            <YAxis type="category" dataKey={spec.xKey} tick={axisTick} width={150} tickLine={false} axisLine={false} interval={0} />
          </>
        ) : (
          <>
            <XAxis dataKey={spec.xKey} tick={axisTick} tickLine={false} axisLine={{ stroke: GRID_COLOR }} interval={0} angle={-20} textAnchor="end" height={64} />
            <YAxis tick={axisTick} tickFormatter={(v) => formatCompact(Number(v))} tickLine={false} axisLine={false} width={48} />
          </>
        )}
        <Tooltip formatter={tooltipFormatter} cursor={{ fill: "rgba(158,104,73,0.09)" }} />
        {spec.series.length > 1 && <Legend />}
        {spec.series.map((s, i) => (
          <Bar key={s} dataKey={s} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={spec.horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
