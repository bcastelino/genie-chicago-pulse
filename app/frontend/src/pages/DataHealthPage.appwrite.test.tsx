import { act, fireEvent, render, screen } from "@testing-library/react";
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
  vi.useRealTimers();
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

  it("wakes once, polls health, and retries the original request when ready", async () => {
    let dataHealthCalls = 0;
    const fetchMock = vi.fn().mockImplementation((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/data-health")) {
        dataHealthCalls += 1;
        if (dataHealthCalls === 1) {
          return Promise.resolve(new Response(JSON.stringify({
            error: "ChicagoPulse live services are currently unavailable.",
            code: "DATABRICKS_APP_UNAVAILABLE",
            wake_available: true,
          }), { status: 503 }));
        }
        return Promise.resolve(new Response(JSON.stringify(health), { status: 200 }));
      }
      if (url.endsWith("/api/runtime/wake")) {
        return Promise.resolve(
          new Response(JSON.stringify({ status: "starting" }), { status: 202 }),
        );
      }
      if (url.endsWith("/api/health")) {
        return Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<DataHealthPage />);

    expect(
      await screen.findByText("Live ChicagoPulse services are unavailable"),
    ).toBeInTheDocument();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Start live service" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Starting ChicagoPulse live services…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Starting live service…" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Starting live service…" }));
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/runtime/wake")),
    ).toHaveLength(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(screen.getByText("Live services are ready.")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Public data view")).toBeInTheDocument();
    expect(dataHealthCalls).toBe(2);
  });

  it("shows a friendly failure when the wake request is refused", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        error: "ChicagoPulse live services are currently unavailable.",
        code: "DATABRICKS_APP_UNAVAILABLE",
        wake_available: true,
      }), { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        error: "ChicagoPulse live services could not be started.",
        code: "DATABRICKS_WAKE_FAILED",
      }), { status: 502 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<DataHealthPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Start live service" }));

    expect(await screen.findByText("Live services could not be started")).toBeInTheDocument();
    expect(screen.getByText(/Free Edition usage limits/i)).toBeInTheDocument();
  });

  it("stops polling after the bounded timeout", async () => {
    const unavailable = () => new Response(JSON.stringify({
      error: "ChicagoPulse live services are currently unavailable.",
      code: "DATABRICKS_APP_UNAVAILABLE",
      wake_available: true,
    }), { status: 503 });
    const fetchMock = vi.fn().mockImplementation((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/api/runtime/wake")) {
        return Promise.resolve(
          new Response(JSON.stringify({ status: "starting" }), { status: 202 }),
        );
      }
      return Promise.resolve(unavailable());
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<DataHealthPage />);
    const start = await screen.findByRole("button", { name: "Start live service" });
    vi.useFakeTimers();
    fireEvent.click(start);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Starting ChicagoPulse live services…")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(92_000);
    });

    expect(screen.getByText("Live services could not be started")).toBeInTheDocument();
    const callsAtTimeout = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(callsAtTimeout);
  });

  it("cancels the pending health poll when the page unmounts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        error: "ChicagoPulse live services are currently unavailable.",
        code: "DATABRICKS_APP_UNAVAILABLE",
        wake_available: true,
      }), { status: 503 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "starting" }), { status: 202 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const view = render(<DataHealthPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Start live service" }));
    await screen.findByText("Starting ChicagoPulse live services…");
    vi.useFakeTimers();
    view.unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
