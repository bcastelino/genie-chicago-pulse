import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResultTable } from "./ResultTable";

describe("ResultTable", () => {
  it("renders headers and formats numeric cells", () => {
    render(
      <ResultTable
        columns={[
          { name: "community_area_name", type: "string" },
          { name: "total", type: "bigint" },
        ]}
        rows={[
          ["Austin", 4820],
          ["Lake View", 5230],
        ]}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "total" })).toBeInTheDocument();
    expect(screen.getByText("4,820")).toBeInTheDocument();
    expect(screen.getByText("Austin")).toBeInTheDocument();
  });

  it("renders an em dash for empty cells", () => {
    render(
      <ResultTable
        columns={[{ name: "x", type: "string" }]}
        rows={[[null]]}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
