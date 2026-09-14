import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config/runtime", () => ({
  apiUrl: (path: string) => `https://proxy.example.appwrite.run${path}`,
  runtimeConfig: {
    apiBaseUrl: "https://proxy.example.appwrite.run",
    deploymentTarget: "appwrite",
  },
}));

import { DataHealthPage } from "./DataHealthPage";

const health = {
  last_refresh_at: "2026-08-25T16:50:21.911Z",
  latest_reporting_month: "July 2026",
  pipeline_status: "operational",
  datasets: [],
  metric_explanation: "Only completed months are reported.",
  source_notice: "City of Chicago open data.",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("DataHealthPage in Appwrite mode", () => {
  it("shows a read-only notice without pipeline actions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(health), { status: 200 }),
      ),
    );

    render(<DataHealthPage />);

    expect(await screen.findByText("Public data view")).toBeInTheDocument();
    expect(
      screen.getByText(/Pipeline controls are available only in the governed Databricks deployment/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /pipeline/i })).not.toBeInTheDocument();
  });
});
