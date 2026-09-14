export type DeploymentTarget = "databricks" | "appwrite";

export interface RuntimeEnvironment {
  VITE_API_BASE_URL?: string;
  VITE_DEPLOYMENT_TARGET?: string;
}

export interface RuntimeConfig {
  apiBaseUrl: string;
  deploymentTarget: DeploymentTarget;
}

export function resolveRuntimeConfig(env: RuntimeEnvironment): RuntimeConfig {
  const rawTarget = env.VITE_DEPLOYMENT_TARGET?.trim() || "databricks";
  if (rawTarget !== "databricks" && rawTarget !== "appwrite") {
    throw new Error(
      `Unsupported VITE_DEPLOYMENT_TARGET: ${rawTarget}. Expected databricks or appwrite.`,
    );
  }

  return {
    deploymentTarget: rawTarget,
    apiBaseUrl: (env.VITE_API_BASE_URL?.trim() || "").replace(/\/+$/, ""),
  };
}

export const runtimeConfig = resolveRuntimeConfig(import.meta.env);

export function apiUrl(path: string, config: RuntimeConfig = runtimeConfig): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${config.apiBaseUrl}${normalizedPath}`;
}
