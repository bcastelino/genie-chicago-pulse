import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LandingPage } from "./LandingPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("LandingPage", () => {
  it("renders the Chicago assembly and both primary destinations", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    );

    const communityAreas = screen.getAllByTestId("hero-fragment");
    expect(communityAreas).toHaveLength(77);
    expect(communityAreas.every((area) => area.tagName.toLowerCase() === "path")).toBe(true);
    expect(screen.getAllByRole("link", { name: /Ask ChicagoPulse/i })[0]).toHaveAttribute("href", "/ask");
    expect(screen.getAllByRole("link", { name: /Explore neighborhoods/i })[0]).toHaveAttribute(
      "href",
      "/neighborhoods",
    );
  });

  it("renders the final static composition when reduced motion is requested", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );

    const { container } = render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    );

    expect(container.querySelector(".hero")).toHaveAttribute("data-motion", "reduced");
    expect(screen.getAllByRole("link", { name: /Ask ChicagoPulse/i })[0]).toHaveAttribute("tabindex", "0");
  });
});
