import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config/runtime", () => ({
  apiUrl: (path: string) => `https://proxy.example.appwrite.run${path}`,
  runtimeConfig: {
    apiBaseUrl: "https://proxy.example.appwrite.run",
    deploymentTarget: "appwrite",
  },
}));

import { NeighborhoodPulsePage } from "./NeighborhoodPulsePage";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("NeighborhoodPulsePage in Appwrite mode", () => {
  it("offers recovery when initial live neighborhood data is unavailable", async () => {
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

    render(<NeighborhoodPulsePage />);

    expect(
      await screen.findByText("Live ChicagoPulse services are unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start live service" })).toBeInTheDocument();
  });
});
