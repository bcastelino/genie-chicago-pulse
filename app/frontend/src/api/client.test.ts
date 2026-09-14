import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("API client runtime URLs", () => {
  it("uses same-origin paths by default", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./client");
    await api.health();

    expect(fetchMock).toHaveBeenCalledWith("/api/health", expect.any(Object));
  });

  it("prefixes paths with the Appwrite Function URL", async () => {
    vi.stubEnv("VITE_DEPLOYMENT_TARGET", "appwrite");
    vi.stubEnv("VITE_API_BASE_URL", "https://proxy.example.appwrite.run/");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./client");
    await api.health();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://proxy.example.appwrite.run/api/health",
      expect.any(Object),
    );
  });

  it("preserves normalized upstream API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Unable to load data." }), { status: 502 }),
      ),
    );

    const { api } = await import("./client");
    await expect(api.dataHealth()).rejects.toEqual(
      expect.objectContaining({ message: "Unable to load data.", status: 502 }),
    );
  });

  it("preserves network error behavior", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    const { api } = await import("./client");
    await expect(api.health()).rejects.toEqual(
      expect.objectContaining({
        message: "Network error. Check your connection and retry.",
        status: 0,
      }),
    );
  });

  it("preserves empty 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    const { api } = await import("./client");
    await expect(
      api.sendMessageFeedback("conversation", "message", {
        rating: "POSITIVE",
        reason: null,
        comment: null,
      }),
    ).resolves.toBeUndefined();
  });
});
