import { describe, expect, it } from "vitest";
import { apiUrl, resolveRuntimeConfig } from "./runtime";

describe("runtime configuration", () => {
  it("defaults to Databricks and same-origin API requests", () => {
    const config = resolveRuntimeConfig({});

    expect(config).toEqual({ deploymentTarget: "databricks", apiBaseUrl: "" });
    expect(apiUrl("/api/health", config)).toBe("/api/health");
  });

  it("keeps a blank API base same-origin", () => {
    const config = resolveRuntimeConfig({
      VITE_DEPLOYMENT_TARGET: "databricks",
      VITE_API_BASE_URL: "   ",
    });

    expect(apiUrl("api/health", config)).toBe("/api/health");
  });

  it("normalizes trailing slashes for Appwrite", () => {
    const config = resolveRuntimeConfig({
      VITE_DEPLOYMENT_TARGET: "appwrite",
      VITE_API_BASE_URL: " https://proxy.example.appwrite.run/// ",
    });

    expect(config.deploymentTarget).toBe("appwrite");
    expect(apiUrl("/api/neighborhoods/compare?areas=1,2", config)).toBe(
      "https://proxy.example.appwrite.run/api/neighborhoods/compare?areas=1,2",
    );
  });

  it("rejects unsupported deployment targets", () => {
    expect(() =>
      resolveRuntimeConfig({ VITE_DEPLOYMENT_TARGET: "preview" }),
    ).toThrow(/Unsupported VITE_DEPLOYMENT_TARGET/);
  });
});
