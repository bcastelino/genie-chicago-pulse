import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { GeoFeature } from "../api/types";
import { ChoroplethMap } from "./ChoroplethMap";

const features: GeoFeature[] = [
  {
    type: "Feature",
    properties: { community_area: 1, community_area_name: "Alpha" },
    geometry: {
      type: "Polygon",
      coordinates: [[[-87.7, 41.9], [-87.65, 41.9], [-87.65, 41.95], [-87.7, 41.95], [-87.7, 41.9]]],
    },
  },
  {
    type: "Feature",
    properties: { community_area: 2, community_area_name: "Beta" },
    geometry: {
      type: "Polygon",
      coordinates: [[[-87.65, 41.9], [-87.6, 41.9], [-87.6, 41.95], [-87.65, 41.95], [-87.65, 41.9]]],
    },
  },
];

describe("ChoroplethMap", () => {
  it("supports pointer and keyboard selection and exposes active details", () => {
    const onSelect = vi.fn();
    const renderResult = render(
      <ChoroplethMap
        features={features}
        values={new Map([[1, 120]])}
        valueLabel="311 Requests"
        selected={[1]}
        onSelect={onSelect}
      />,
    );

    const { container } = renderResult;
    const alpha = screen.getByRole("button", { name: "Alpha: 120 311 Requests" });
    const beta = screen.getByRole("button", { name: "Beta: no data" });
    expect(alpha).toHaveClass("selected");
    expect(container.querySelector('.choropleth__selection-outline[data-community-area="1"]')).toHaveAttribute(
      "vector-effect",
      "non-scaling-stroke",
    );

    fireEvent.mouseEnter(beta);
    expect(screen.getByText("No 311 requests data")).toBeInTheDocument();
    fireEvent.focus(beta);
    expect(container.querySelector('.choropleth__focus-outline[data-community-area="2"]')).toBeInTheDocument();
    fireEvent.click(beta);
    fireEvent.keyDown(alpha, { key: " " });

    expect(onSelect).toHaveBeenNthCalledWith(1, 2);
    expect(onSelect).toHaveBeenNthCalledWith(2, 1);
  });

  it("replaces mock grid cells with all 77 local community-area boundaries", () => {
    const mockGrid = Array.from({ length: 12 }, (_, index): GeoFeature => {
      const x = -87.9 + (index % 4) * 0.06;
      const y = 41.65 + Math.floor(index / 4) * 0.05;
      return {
        type: "Feature",
        properties: { community_area: index + 20, community_area_name: `Mock ${index + 20}` },
        geometry: {
          type: "Polygon",
          coordinates: [[[x, y], [x + 0.05, y], [x + 0.05, y + 0.04], [x, y + 0.04], [x, y]]],
        },
      };
    });

    render(
      <ChoroplethMap
        features={mockGrid}
        values={new Map()}
        valueLabel="311 Requests"
        selected={[]}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("button")).toHaveLength(77);
    expect(screen.getByRole("button", { name: "Rogers Park: no data" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "O'Hare: no data" })).toBeInTheDocument();
  });
});
