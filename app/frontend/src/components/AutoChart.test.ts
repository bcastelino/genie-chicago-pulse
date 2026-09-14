import { describe, expect, it } from "vitest";
import type { Column } from "../api/types";
import { chooseChart } from "./AutoChart";

const cols = (names: string[]): Column[] => names.map((n) => ({ name: n, type: "string" }));

describe("chooseChart", () => {
  it("uses a line chart for a time series", () => {
    const spec = chooseChart(cols(["metric_month", "total_311_requests"]), [
      ["2024-05-01", 4210],
      ["2024-06-01", 4820],
    ]);
    expect(spec.kind).toBe("line");
    if (spec.kind === "line") expect(spec.xKey).toBe("metric_month");
  });

  it("uses a horizontal bar for one category + one measure", () => {
    const spec = chooseChart(cols(["community_area_name", "total"]), [
      ["Austin", 4820],
      ["Lake View", 5230],
    ]);
    expect(spec.kind).toBe("bar");
    if (spec.kind === "bar") expect(spec.horizontal).toBe(true);
  });

  it("uses a grouped bar for one category + multiple measures", () => {
    const spec = chooseChart(cols(["name", "requests", "violations"]), [
      ["Austin", 4820, 512],
      ["Lake View", 5230, 96],
    ]);
    expect(spec.kind).toBe("bar");
    if (spec.kind === "bar") {
      expect(spec.horizontal).toBe(false);
      expect(spec.series).toEqual(["requests", "violations"]);
    }
  });

  it("falls back to none for non-chartable data", () => {
    const spec = chooseChart(cols(["a", "b"]), [["x", "y"]]);
    expect(spec.kind).toBe("none");
  });
});
