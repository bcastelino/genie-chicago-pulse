import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("renders a formatted value and delta", () => {
    render(
      <MetricCard label="311 Requests" value={4820} momPct={14.49} higherIsBetter={false} />,
    );
    expect(screen.getByText("4,820")).toBeInTheDocument();
    expect(screen.getByText(/14\.5%/)).toBeInTheDocument();
  });

  it("renders N/A when data is unavailable, never 0", () => {
    render(<MetricCard label="Business Licenses" value={null} available={false} />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });
});
