import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("App routing", () => {
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
