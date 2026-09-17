import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "../api/client";
import type {
  ComparisonResponse,
  GeoFeatureCollection,
  MapMetricResponse,
  Neighborhood,
  NeighborhoodPulse,
} from "../api/types";
import { AutoChart, ChoroplethMap } from "../components/lazy";
import { MetricCard } from "../components/MetricCard";
import { LiveServiceErrorState } from "../components/LiveServiceErrorState";
import { NeighborhoodSelect } from "../components/NeighborhoodSelect";
import { ResultTable } from "../components/ResultTable";
import { EmptyState, ErrorState, Skeleton } from "../components/States";
import { IconChart } from "../components/icons";
import { formatNumber } from "../lib/format";

interface MetricMeta {
  higherIsBetter?: boolean;
  decimals?: number;
}
const META: Record<string, MetricMeta> = {
  total_311_requests: { higherIsBetter: false },
  open_311_requests: { higherIsBetter: false },
  avg_resolution_days: { higherIsBetter: false, decimals: 1 },
  business_license_issues: { higherIsBetter: true },
  building_permits: { higherIsBetter: true },
  building_violations: { higherIsBetter: false },
};

const DEFAULT_CA = 25; // Austin

function MetricCardsSkeleton() {
  return (
    <div className="grid grid--metrics">
      {Array.from({ length: 6 }).map((_, i) => (
        <div className="metric" key={i}>
          <Skeleton width="60%" height={12} />
          <div style={{ height: 8 }} />
          <Skeleton width="70%" height={28} />
        </div>
      ))}
    </div>
  );
}

function PulseMetricGrid({
  pulse,
  loading,
  error,
  onRetry,
}: {
  pulse: NeighborhoodPulse | null;
  loading: boolean;
  error: ApiError | null;
  onRetry: () => void;
}) {
  if (loading) return <MetricCardsSkeleton />;
  if (error) return <LiveServiceErrorState error={error} onRetry={onRetry} />;
  if (!pulse) {
    return <EmptyState title="No data yet" message="This neighborhood has no metrics for the latest month." />;
  }
  return (
    <div className="grid grid--metrics">
      {pulse.metrics.map((metric) => (
        <MetricCard
          key={metric.key}
          label={metric.label}
          value={metric.value}
          unit={metric.unit}
          decimals={META[metric.key]?.decimals ?? 0}
          momPct={metric.mom_change_pct}
          higherIsBetter={META[metric.key]?.higherIsBetter}
          available={metric.available}
        />
      ))}
    </div>
  );
}

export function NeighborhoodPulsePage() {
  const [neighborhoods, setNeighborhoods] = useState<Neighborhood[]>([]);
  const [geo, setGeo] = useState<GeoFeatureCollection | null>(null);
  const [mapData, setMapData] = useState<MapMetricResponse | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [pulse, setPulse] = useState<NeighborhoodPulse | null>(null);
  const [pulseLoading, setPulseLoading] = useState(true);
  const [pulseError, setPulseError] = useState<ApiError | null>(null);
  const [initError, setInitError] = useState<ApiError | null>(null);

  const [compareCas, setCompareCas] = useState<number[]>([]);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);

  const loadInit = useCallback(async () => {
    setInitError(null);
    try {
      const [ns, g, m] = await Promise.all([
        api.neighborhoods(),
        api.neighborhoodsGeo().catch(() => null),
        api.neighborhoodsMap().catch(() => null),
      ]);
      setNeighborhoods(ns);
      setGeo(g);
      setMapData(m);
      const initial = ns.find((n) => n.community_area === DEFAULT_CA)?.community_area ?? ns[0]?.community_area ?? null;
      setSelected(initial);
      if (initial) setCompareCas([initial]);
    } catch (err) {
      setInitError(
        err instanceof ApiError
          ? err
          : new ApiError("Unable to load neighborhoods.", 0),
      );
    }
  }, []);

  useEffect(() => {
    loadInit();
  }, [loadInit]);

  const loadPulse = useCallback(async (ca: number) => {
    setPulseLoading(true);
    setPulseError(null);
    try {
      setPulse(await api.pulse(ca));
    } catch (err) {
      setPulse(null);
      setPulseError(
        err instanceof ApiError
          ? err
          : new ApiError("Unable to load neighborhood data.", 0),
      );
    } finally {
      setPulseLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected != null) loadPulse(selected);
  }, [selected, loadPulse]);

  useEffect(() => {
    if (compareCas.length < 2) {
      setComparison(null);
      setCompareError(null);
      return;
    }
    let active = true;
    api
      .compare(compareCas)
      .then((c) => active && setComparison(c))
      .catch((err) => active && setCompareError(err instanceof ApiError ? err.message : "Unable to compare."));
    return () => {
      active = false;
    };
  }, [compareCas]);

  const options = useMemo(
    () => neighborhoods.map((n) => ({ value: n.community_area, label: n.community_area_name })),
    [neighborhoods],
  );

  const mapValues = useMemo(() => {
    const map = new Map<number, number>();
    mapData?.values.forEach((v) => {
      if (v.value != null) map.set(v.community_area, v.value);
    });
    return map;
  }, [mapData]);

  const addCompare = (ca: number) => {
    setCompareCas((prev) => (prev.includes(ca) || prev.length >= 4 ? prev : [...prev, ca]));
  };
  const removeCompare = (ca: number) => setCompareCas((prev) => prev.filter((c) => c !== ca));

  if (initError) {
    return (
      <div className="stack">
        <div className="page-head">
          <h1>Neighborhood Pulse</h1>
        </div>
        <div className="card card--pad">
          <LiveServiceErrorState error={initError} onRetry={loadInit} />
        </div>
      </div>
    );
  }

  return (
    <div className="neighborhood-page">
      <section className="map-workspace" aria-labelledby="neighborhood-pulse-title">
        <aside className="map-rail">
          <div className="map-rail__intro">
            <span className="overline">Chicago by community area</span>
            <h1 id="neighborhood-pulse-title">Neighborhood Pulse</h1>
            <p>
              Explore governed monthly metrics across Chicago’s 77 community areas for the latest
              completed reporting month.
            </p>
          </div>

          <div className="map-rail__controls">
            <NeighborhoodSelect
              id="primary-neighborhood"
              label="Neighborhood"
              options={options}
              value={selected}
              onChange={setSelected}
            />
            <div className="map-period">
              <span className="overline">Reporting period</span>
              <strong>{pulse?.reporting_period_label ?? mapData?.reporting_period_label ?? "Latest completed month"}</strong>
            </div>
            {selected != null && !compareCas.includes(selected) && (
              <button className="btn" onClick={() => addCompare(selected)} disabled={compareCas.length >= 4}>
                Add to compare
              </button>
            )}
          </div>

          <section className="map-rail__metrics" aria-label="Key metrics">
            <PulseMetricGrid
              pulse={pulse}
              loading={pulseLoading}
              error={pulseError}
              onRetry={() => selected != null && loadPulse(selected)}
            />
          </section>
        </aside>

        <div className="map-panel card">
          <div className="map-panel__head">
            <div>
              <span className="overline">Citywide signal</span>
              <h2>311 requests by community area</h2>
            </div>
            <span className="map-panel__hint">Select an area to view its pulse</span>
          </div>
          <div className="map-panel__body">
            {geo && geo.features.length ? (
              <ChoroplethMap
                features={geo.features}
                values={mapValues}
                valueLabel={mapData?.metric_label ?? "311 Requests"}
                selected={selected != null ? [selected] : []}
                onSelect={setSelected}
              />
            ) : (
              <EmptyState
                title="Map unavailable"
                message="Community-area boundaries could not be loaded for this environment."
              />
            )}
          </div>
        </div>
      </section>

      <section className="neighborhood-analysis" aria-label="Neighborhood analysis">
        <div className="grid grid--2 neighborhood-analysis__charts">
          <div className="card card--pad">
            <div className="card__head">
              <div className="card__title">12-month 311 trend</div>
              <div className="card__sub">{pulse?.community_area_name}</div>
            </div>
            {pulseLoading ? (
              <Skeleton height={280} radius={8} />
            ) : pulse && pulse.trend_311.length ? (
              <AutoChart
                columns={[
                  { name: "metric_month", type: "date" },
                  { name: "311 Requests", type: "number" },
                ]}
                rows={pulse.trend_311.map((trend) => [trend.metric_month, trend.value])}
                spec={{ kind: "line", xKey: "metric_month", series: ["311 Requests"], xIsMonth: true }}
              />
            ) : (
              <EmptyState title="No trend data" />
            )}
          </div>

          <div className="card card--pad">
            <div className="card__head">
              <div className="card__title">Top 311 service request types</div>
              <div className="card__sub">{pulse?.reporting_period_label}</div>
            </div>
            {pulseLoading ? (
              <Skeleton height={260} radius={8} />
            ) : pulse && pulse.top_service_types.length ? (
              <AutoChart
                columns={[
                  { name: "Service type", type: "string" },
                  { name: "Requests", type: "number" },
                ]}
                rows={pulse.top_service_types.map((category) => [category.category, category.value])}
                spec={{ kind: "bar", xKey: "Service type", series: ["Requests"], horizontal: true, xIsMonth: false }}
              />
            ) : (
              <EmptyState title="No service-type data" />
            )}
          </div>
        </div>

        <ComparisonSection
          options={options}
          compareCas={compareCas}
          neighborhoods={neighborhoods}
          comparison={comparison}
          error={compareError}
          onAdd={addCompare}
          onRemove={removeCompare}
        />
      </section>
    </div>
  );
}

function ComparisonSection({
  options,
  compareCas,
  neighborhoods,
  comparison,
  error,
  onAdd,
  onRemove,
}: {
  options: { value: number; label: string }[];
  compareCas: number[];
  neighborhoods: Neighborhood[];
  comparison: ComparisonResponse | null;
  error: string | null;
  onAdd: (ca: number) => void;
  onRemove: (ca: number) => void;
}) {
  const nameOf = (ca: number) => neighborhoods.find((n) => n.community_area === ca)?.community_area_name ?? `#${ca}`;

  const chartData = useMemo(() => {
    if (!comparison) return null;
    const rows = comparison.neighborhoods.map((n) => [
      n.community_area_name,
      n.metrics.find((m) => m.key === "total_311_requests")?.value ?? null,
      n.metrics.find((m) => m.key === "building_violations")?.value ?? null,
    ]);
    return rows;
  }, [comparison]);

  // Comparison table: metrics as rows, neighborhoods as columns.
  const tableColumns = comparison
    ? [{ name: "Metric", type: "string" }, ...comparison.neighborhoods.map((n) => ({ name: n.community_area_name, type: "number" }))]
    : [];
  const tableRows =
    comparison && comparison.metric_keys.length
      ? comparison.metric_keys.map((mk) => [
          mk.label,
          ...comparison.neighborhoods.map((n) => {
            const m = n.metrics.find((x) => x.key === mk.key);
            if (!m || !m.available || m.value == null) return "N/A";
            return formatNumber(m.value, { decimals: mk.key === "avg_resolution_days" ? 1 : 0 });
          }),
        ])
      : [];

  return (
    <div className="card card--pad">
      <div className="card__head">
        <div className="card__title">Compare neighborhoods</div>
        <div className="card__sub">
          {comparison?.reporting_period_label ?? "Latest completed month"} · up to 4
        </div>
      </div>

      <div className="toolbar" style={{ marginBottom: "var(--sp-4)" }}>
        <div style={{ minWidth: 260, flex: 1 }}>
          <NeighborhoodSelect
            id="compare-neighborhood"
            label="Add a neighborhood"
            options={options.filter((o) => !compareCas.includes(o.value))}
            value={null}
            onChange={onAdd}
          />
        </div>
      </div>

      <div className="row" style={{ marginBottom: "var(--sp-4)" }}>
        {compareCas.map((ca) => (
          <span key={ca} className="chip chip--selected" style={{ cursor: "default" }}>
            {nameOf(ca)}
            <button
              className="btn btn--ghost btn--sm"
              style={{ minHeight: 20, padding: 2, marginLeft: 4 }}
              aria-label={`Remove ${nameOf(ca)} from comparison`}
              onClick={() => onRemove(ca)}
            >
              ✕
            </button>
          </span>
        ))}
        {compareCas.length < 2 && <span className="help">Add at least two neighborhoods to compare.</span>}
      </div>

      {error && <ErrorState message={error} />}

      {comparison && chartData && (
        <div className="stack" style={{ gap: "var(--sp-5)" }}>
          <div>
            <div className="card__sub" style={{ marginBottom: "var(--sp-2)" }}>
              <IconChart size={14} /> 311 requests vs. building violations
            </div>
            <AutoChart
              columns={[
                { name: "Neighborhood", type: "string" },
                { name: "311 Requests", type: "number" },
                { name: "Building Violations", type: "number" },
              ]}
              rows={chartData}
              spec={{
                kind: "bar",
                xKey: "Neighborhood",
                series: ["311 Requests", "Building Violations"],
                horizontal: false,
                xIsMonth: false,
              }}
            />
          </div>
          <ResultTable columns={tableColumns} rows={tableRows} caption="Neighborhood comparison" />
        </div>
      )}
    </div>
  );
}
