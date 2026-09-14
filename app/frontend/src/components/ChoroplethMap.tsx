import { geoIdentity, geoPath } from "d3-geo";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GeoFeature } from "../api/types";
import { CHICAGO_COMMUNITY_PATHS } from "../data/chicagoCommunityPaths";
import { formatCompact } from "../lib/format";

const W = 640;
const H = 440;
const LOW = [240, 222, 213]; // warm clay tint
const MID = [185, 132, 89]; // rust
const HIGH = [32, 54, 70]; // lake navy
const LOCAL_VIEWBOX = { width: 528, height: 520 };

function isAxisAlignedGridCell(feature: GeoFeature): boolean {
  const geometry = feature.geometry as { type?: string; coordinates?: unknown } | null;
  if (geometry?.type !== "Polygon" || !Array.isArray(geometry.coordinates)) return false;
  const ring = geometry.coordinates[0];
  if (!Array.isArray(ring) || ring.length !== 5) return false;
  const points = ring.filter(
    (point): point is [number, number] =>
      Array.isArray(point) && point.length >= 2 && typeof point[0] === "number" && typeof point[1] === "number",
  );
  if (points.length !== 5) return false;
  return new Set(points.map(([x]) => x)).size === 2 && new Set(points.map(([, y]) => y)).size === 2;
}

function communityName(name: string): string {
  return name
    .toLowerCase()
    .replace(/\b[a-z]/g, (letter) => letter.toUpperCase())
    .replace("Ohare", "O'Hare")
    .replace("Mckinley", "McKinley");
}

function lerpColor(t: number): string {
  const from = t < 0.55 ? LOW : MID;
  const to = t < 0.55 ? MID : HIGH;
  const local = t < 0.55 ? t / 0.55 : (t - 0.55) / 0.45;
  const c = from.map((start, i) => Math.round(start + (to[i] - start) * local));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export function ChoroplethMap({
  features,
  values,
  valueLabel,
  selected,
  onSelect,
}: {
  features: GeoFeature[];
  values: Map<number, number>;
  valueLabel: string;
  selected: number[];
  onSelect: (communityArea: number) => void;
}) {
  const [active, setActive] = useState<number | null>(selected[0] ?? null);
  const [focused, setFocused] = useState<number | null>(null);
  const pointerDown = useRef(false);

  useEffect(() => {
    setActive(selected[0] ?? null);
  }, [selected]);

  const { paths, min, max } = useMemo(() => {
    const nums = [...values.values()].filter((v) => Number.isFinite(v));
    const lo = nums.length ? Math.min(...nums) : 0;
    const hi = nums.length ? Math.max(...nums) : 1;
    const stylePath = (ca: number, name: string, d: string, transform?: string) => {
      const v = values.get(ca);
      const t = v === undefined || hi === lo ? 0 : (v - lo) / (hi - lo);
      return {
        ca,
        name,
        d,
        transform,
        fill: v === undefined ? "#e8ddd6" : lerpColor(t),
        value: v,
      };
    };

    // Mock mode deliberately returns simple grid cells. Replace only that
    // placeholder geometry with the same local 77-area map used by the hero.
    const usesMockGrid = features.length >= 12 && features.every(isAxisAlignedGridCell);
    let paths;
    if (usesMockGrid) {
      const names = new Map(
        features.map((feature) => [feature.properties.community_area, feature.properties.community_area_name]),
      );
      const scale = (H - 16) / LOCAL_VIEWBOX.height;
      const x = (W - LOCAL_VIEWBOX.width * scale) / 2;
      const transform = `translate(${x.toFixed(2)} 8) scale(${scale.toFixed(4)})`;
      paths = CHICAGO_COMMUNITY_PATHS.map((area) =>
        stylePath(area.id, names.get(area.id) ?? communityName(area.name), area.d, transform),
      );
    } else {
      const collection = { type: "FeatureCollection", features };
      // Governed boundaries are already local planar shapes. geoIdentity
      // avoids spherical ring-winding rules that can fill the world rectangle.
      const projection = geoIdentity().reflectY(true).fitExtent([[8, 8], [W - 8, H - 8]], collection as never);
      const path = geoPath(projection);
      paths = features.map((feature) =>
        stylePath(
          feature.properties.community_area,
          feature.properties.community_area_name,
          path(feature as never) ?? "",
        ),
      );
    }
    return { paths, min: lo, max: hi };
  }, [features, values]);

  const activePath = paths.find((path) => path.ca === active);
  const selectedPaths = paths.filter((path) => selected.includes(path.ca));
  const focusedPath = paths.find((path) => path.ca === focused);

  return (
    <div className="choropleth-shell">
      <div className="choropleth-stage">
        <svg
          className="choropleth"
          viewBox={`0 0 ${W} ${H}`}
          role="group"
          aria-label={`Map of Chicago community areas shaded by ${valueLabel}`}
        >
          {paths.map((path) => (
            <path
              key={path.ca}
              d={path.d}
              transform={path.transform}
              fill={path.fill}
              vectorEffect="non-scaling-stroke"
              className={`choropleth__area${selected.includes(path.ca) ? " selected" : ""}`}
              tabIndex={0}
              role="button"
              aria-label={`${path.name}: ${path.value === undefined ? "no data" : `${formatCompact(path.value)} ${valueLabel}`}`}
              onMouseEnter={() => setActive(path.ca)}
              onMouseLeave={() => setActive(selected[0] ?? null)}
              onPointerDown={() => {
                pointerDown.current = true;
                setFocused(null);
              }}
              onPointerUp={() => {
                pointerDown.current = false;
              }}
              onPointerCancel={() => {
                pointerDown.current = false;
              }}
              onFocus={() => {
                setActive(path.ca);
                if (!pointerDown.current) setFocused(path.ca);
              }}
              onBlur={() => {
                setActive(selected[0] ?? null);
                setFocused(null);
              }}
              onClick={() => onSelect(path.ca)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(path.ca);
                }
              }}
            >
              <title>
                {path.name}: {path.value === undefined ? "no data" : `${formatCompact(path.value)} ${valueLabel}`}
              </title>
            </path>
          ))}
          <g aria-hidden="true" className="choropleth__outline-layer">
            {selectedPaths.map((path) => (
              <path
                key={`selected-${path.ca}`}
                d={path.d}
                transform={path.transform}
                vectorEffect="non-scaling-stroke"
                className="choropleth__selection-outline"
                data-community-area={path.ca}
              />
            ))}
            {focusedPath && (
              <path
                d={focusedPath.d}
                transform={focusedPath.transform}
                vectorEffect="non-scaling-stroke"
                className="choropleth__focus-outline"
                data-community-area={focusedPath.ca}
              />
            )}
          </g>
        </svg>
        <div className="map-readout" aria-live="polite">
          <span className="overline">{activePath ? "Community area" : "Explore the map"}</span>
          <strong>{activePath?.name ?? "Choose an area"}</strong>
          <span>
            {activePath
              ? activePath.value === undefined
                ? `No ${valueLabel.toLowerCase()} data`
                : `${formatCompact(activePath.value)} ${valueLabel}`
              : "Hover, focus, or select a boundary"}
          </span>
        </div>
      </div>
      <div className="legend" style={{ marginTop: "var(--sp-3)" }}>
        <span>{valueLabel}</span>
        <span className="tnum">{formatCompact(min)}</span>
        <span
          className="legend__scale"
          style={{ background: `linear-gradient(90deg, ${lerpColor(0)}, ${lerpColor(1)})` }}
        />
        <span className="tnum">{formatCompact(max)}</span>
      </div>
    </div>
  );
}
