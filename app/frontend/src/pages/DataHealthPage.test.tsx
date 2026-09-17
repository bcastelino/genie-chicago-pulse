import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DataHealthPage } from "./DataHealthPage";

const health = {
  last_refresh_at: "2026-08-25T16:50:21.911Z",
  latest_reporting_month: "July 2026",
  pipeline_status: "operational",
  datasets: [
    {
      dataset: "311 Service Requests",
      socrata_id: "v6vf-nfxy",
      category: "Service Requests",
      source_url: "https://data.cityofchicago.org/d/v6vf-nfxy",
      usage_status: "in_use",
      row_count: 1200,
      min_date: "2026-07-01",
      max_date: "2026-07-31",
      last_ingested_at: "2026-08-25T16:40:00Z",
    },
    {
      dataset: "Food Inspections",
      socrata_id: "4ijn-s7e5",
      category: "Health & Human Services",
      source_url: "https://data.cityofchicago.org/d/4ijn-s7e5",
      usage_status: "future_scope",
      row_count: null,
      min_date: null,
      max_date: null,
      last_ingested_at: null,
    },
  ],
  metric_explanation: "Only completed months are reported.",
  source_notice: "City of Chicago open data.",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("DataHealthPage pipeline control", () => {
  it("keeps the normal error state in the Databricks deployment", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({
          error: "ChicagoPulse live services are currently unavailable.",
          code: "DATABRICKS_APP_UNAVAILABLE",
          wake_available: true,
        }), { status: 503 }),
      ),
    );

    render(<DataHealthPage />);

    expect(
      await screen.findByText("ChicagoPulse live services are currently unavailable."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start live service" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try Again" })).toBeInTheDocument();
  });

  it("opens inline confirmation before triggering the allowlisted pipeline endpoint", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(health), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        run_id: 424242,
        life_cycle_state: "PENDING",
        result_state: null,
        run_page_url: null,
        started_new: true,
        start_time: null,
        end_time: null,
        duration_ms: null,
        tasks: [
          { task_key: "incremental_ingestion", label: "Incremental ingestion", life_cycle_state: "PENDING", result_state: null, start_time: null, end_time: null, duration_ms: null },
          { task_key: "transform_refresh", label: "Transform refresh", life_cycle_state: "PENDING", result_state: null, start_time: null, end_time: null, duration_ms: null },
          { task_key: "validation", label: "Validation", life_cycle_state: "PENDING", result_state: null, start_time: null, end_time: null, duration_ms: null },
        ],
      }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<DataHealthPage />);
    await screen.findByText("Operational");
    const sourceTable = screen.getByRole("table", {
      name: "ChicagoPulse source datasets and ingestion coverage",
    });
    expect(within(sourceTable).getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "Dataset",
      "Status",
      "Category",
      "Socrata ID",
      "Rows",
      "Coverage",
      "Last ingested",
    ]);
    expect(within(sourceTable).getAllByRole("row")).toHaveLength(health.datasets.length + 1);
    expect(within(sourceTable).getByRole("link", { name: "311 Service Requests" })).toHaveAttribute(
      "href",
      "https://data.cityofchicago.org/d/v6vf-nfxy",
    );
    expect(screen.getByRole("link", { name: "Visit the City of Chicago Data Portal" })).toHaveAttribute(
      "href",
      "https://data.cityofchicago.org/",
    );
    expect(screen.getByText("In ChicagoPulse")).toBeInTheDocument();
    expect(screen.getByText("Potential future source")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Food Inspections" })).toHaveAttribute(
      "href",
      "https://data.cityofchicago.org/d/4ijn-s7e5",
    );
    fireEvent.click(screen.getByRole("button", { name: "Run pipeline now" }));
    expect(await screen.findByRole("heading", { name: /Start ChicagoPulse Daily Refresh/i })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Start pipeline" }));

    expect(await screen.findByText("Refresh queued")).toBeInTheDocument();
    expect(screen.getByText("424242")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/data-health/pipeline-runs",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("can cancel preflight without starting compute", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(health), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<DataHealthPage />);
    await screen.findByText("Operational");
    fireEvent.click(screen.getByRole("button", { name: "Run pipeline now" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("heading", { name: /Start ChicagoPulse Daily Refresh/i })).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
