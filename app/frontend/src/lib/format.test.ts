import { describe, expect, it } from "vitest";
import { formatCompact, formatNumber, formatPercent, monthLabel, monthShort } from "./format";

describe("format", () => {
  it("formats numbers with grouping", () => {
    expect(formatNumber(4820)).toBe("4,820");
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(3.14159, { decimals: 1 })).toBe("3.1");
  });

  it("formats compact large numbers", () => {
    expect(formatCompact(14500000)).toMatch(/M/);
    expect(formatCompact(500)).toBe("500");
  });

  it("formats signed percentages", () => {
    expect(formatPercent(14.49)).toBe("+14.5%");
    expect(formatPercent(-5.1)).toBe("-5.1%");
    expect(formatPercent(null)).toBe("—");
  });

  it("labels months", () => {
    expect(monthLabel("2024-06-01T00:00:00Z")).toBe("June 2024");
    expect(monthLabel("2024-06")).toBe("June 2024");
    expect(monthShort("2024-06-01")).toBe("Jun \u201924");
  });
});
