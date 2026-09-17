import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("App routing", () => {
  it("does not wake live services when the homepage renders", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        error: "ChicagoPulse live services are currently unavailable.",
        code: "DATABRICKS_APP_UNAVAILABLE",
        wake_available: true,
      }), { status: 503 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Chicago, in motion/i)).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).endsWith("/api/runtime/wake")),
    ).toBe(false);
    expect(screen.queryByRole("button", { name: "Start live service" })).not.toBeInTheDocument();
  });

  it("lets direct working routes bypass the landing hero", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok", mock_mode: true, environment: "test", version: "test" }), {
          status: 200,
        }),
      ),
    );

    render(
      <MemoryRouter initialEntries={["/ask"]}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Ask ChicagoPulse" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.queryByText(/Chicago, in motion/i)).not.toBeInTheDocument();
  });
});
