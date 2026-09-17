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

  it("preserves the structured Appwrite service-unavailable error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: "ChicagoPulse live services are currently unavailable.",
            code: "DATABRICKS_APP_UNAVAILABLE",
            wake_available: true,
          }),
          { status: 503 },
        ),
      ),
    );

    const { api } = await import("./client");
    await expect(api.dataHealth()).rejects.toEqual(
      expect.objectContaining({
        status: 503,
        code: "DATABRICKS_APP_UNAVAILABLE",
        wakeAvailable: true,
      }),
    );
  });

  it("posts to the fixed runtime wake endpoint", async () => {
    vi.stubEnv("VITE_DEPLOYMENT_TARGET", "appwrite");
    vi.stubEnv("VITE_API_BASE_URL", "https://proxy.example.appwrite.run");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "starting" }), { status: 202 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./client");
    await expect(api.wakeRuntime()).resolves.toEqual({ status: "starting" });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://proxy.example.appwrite.run/api/runtime/wake",
      expect.objectContaining({ method: "POST" }),
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
