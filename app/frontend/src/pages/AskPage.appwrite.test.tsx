import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../config/runtime", () => ({
  apiUrl: (path: string) => `https://proxy.example.appwrite.run${path}`,
  runtimeConfig: {
    apiBaseUrl: "https://proxy.example.appwrite.run",
    deploymentTarget: "appwrite",
  },
}));

import { AskPage } from "./AskPage";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AskPage in Appwrite mode", () => {
  it("offers recovery when Genie agent initialization finds the service stopped", async () => {
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

    render(<AskPage />);

    expect(
      await screen.findByText("Live ChicagoPulse services are unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start live service" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Your question")).not.toBeInTheDocument();
  });
});
