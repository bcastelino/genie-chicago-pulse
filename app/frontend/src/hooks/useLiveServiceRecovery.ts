import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import { runtimeConfig } from "../config/runtime";

const HEALTH_POLL_INTERVAL_MS = 4_000;
const HEALTH_POLL_TIMEOUT_MS = 90_000;
const READY_ANNOUNCEMENT_MS = 500;

export type LiveServiceRecoveryPhase =
  | "unavailable"
  | "starting"
  | "ready"
  | "failed";

export function isWakeableServiceError(
  error: ApiError | null | undefined,
): boolean {
  return Boolean(
    runtimeConfig.deploymentTarget === "appwrite" &&
      error?.code === "DATABRICKS_APP_UNAVAILABLE" &&
      error.wakeAvailable === true,
  );
}

function canKeepPolling(error: unknown): boolean {
  return (
    !(error instanceof ApiError) ||
    error.status === 0 ||
    error.status === 502 ||
    error.status === 503 ||
    error.status === 504
  );
}

export function useLiveServiceRecovery(
  error: ApiError,
  onRecovered: () => void | Promise<void>,
) {
  const [phase, setPhase] = useState<LiveServiceRecoveryPhase>("unavailable");
  const mountedRef = useRef(true);
  const activeRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const onRecoveredRef = useRef(onRecovered);

  useEffect(() => {
    onRecoveredRef.current = onRecovered;
  }, [onRecovered]);

  const stopPolling = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      activeRef.current = false;
      stopPolling();
    };
  }, [stopPolling]);

  useEffect(() => {
    if (!activeRef.current) setPhase("unavailable");
  }, [error]);

  const finishRecovery = useCallback(() => {
    if (!mountedRef.current) return;
    stopPolling();
    setPhase("ready");
    timerRef.current = window.setTimeout(() => {
      if (!mountedRef.current) return;
      activeRef.current = false;
      void onRecoveredRef.current();
    }, READY_ANNOUNCEMENT_MS);
  }, [stopPolling]);

  const pollHealth = useCallback(
    (deadline: number) => {
      if (!mountedRef.current || !activeRef.current) return;
      if (Date.now() >= deadline) {
        activeRef.current = false;
        setPhase("failed");
        return;
      }

      timerRef.current = window.setTimeout(async () => {
        if (!mountedRef.current || !activeRef.current) return;
        const controller = new AbortController();
        controllerRef.current = controller;
        try {
          await api.health({ signal: controller.signal });
          finishRecovery();
        } catch (pollError) {
          if (!mountedRef.current || controller.signal.aborted) return;
          controllerRef.current = null;
          if (!canKeepPolling(pollError) || Date.now() >= deadline) {
            activeRef.current = false;
            setPhase("failed");
            return;
          }
          pollHealth(deadline);
        }
      }, HEALTH_POLL_INTERVAL_MS);
    },
    [finishRecovery],
  );

  const start = useCallback(async () => {
    if (!isWakeableServiceError(error) || activeRef.current) return;
    stopPolling();
    activeRef.current = true;
    setPhase("starting");
    try {
      const result = await api.wakeRuntime();
      if (!mountedRef.current) return;
      if (result.status === "ready") {
        finishRecovery();
        return;
      }
      pollHealth(Date.now() + HEALTH_POLL_TIMEOUT_MS);
    } catch {
      if (!mountedRef.current) return;
      activeRef.current = false;
      setPhase("failed");
    }
  }, [error, finishRecovery, pollHealth, stopPolling]);

  return { phase, start };
}
