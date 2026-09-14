import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PipelineRunResponse } from "../api/types";
import { PipelineRunPanel } from "./PipelineRunPanel";

const run: PipelineRunResponse = {
  run_id: 424242,
  life_cycle_state: "RUNNING",
  result_state: null,
  run_page_url: "https://example.databricks.com/run/424242",
  started_new: true,
  start_time: "2026-08-27T14:00:00Z",
  end_time: null,
  duration_ms: 90000,
  tasks: [
    { task_key: "incremental_ingestion", label: "Incremental ingestion", life_cycle_state: "TERMINATED", result_state: "SUCCESS", start_time: null, end_time: null, duration_ms: 60000 },
    { task_key: "transform_refresh", label: "Transform refresh", life_cycle_state: "RUNNING", result_state: null, start_time: null, end_time: null, duration_ms: null },
    { task_key: "validation", label: "Validation", life_cycle_state: "PENDING", result_state: null, start_time: null, end_time: null, duration_ms: null },
  ],
};

const handlers = { onStart: vi.fn(), onCancel: vi.fn(), onCollapse: vi.fn() };

describe("PipelineRunPanel", () => {
  it("renders real ordered task states and run provenance", () => {
    render(
      <PipelineRunPanel mode="run" run={run} starting={false} error={null} {...handlers} />,
    );
    const stages = within(screen.getByRole("list", { name: "Pipeline stages" }));
    expect(stages.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      expect.stringContaining("Incremental ingestionSucceeded"),
      expect.stringContaining("Transform refreshRunning"),
      expect.stringContaining("ValidationQueued"),
    ]);
    expect(screen.getByRole("link", { name: /View run in Databricks/i })).toHaveAttribute(
      "href",
      run.run_page_url,
    );
  });

  it("renders terminal failure and a safe polling error", () => {
    const failed = {
      ...run,
      life_cycle_state: "TERMINATED",
      result_state: "FAILED",
      end_time: "2026-08-27T14:02:00Z",
    };
    render(
      <PipelineRunPanel mode="run" run={failed} starting={false} error="Unable to check pipeline run status." {...handlers} />,
    );
    expect(screen.getByText("Refresh failed")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to check pipeline run status.");
  });
});
