// Typed API client. Databricks uses same-origin /api calls; Appwrite prefixes
// the same paths with its configured Function domain.

import type {
  ComparisonResponse,
  ConversationCreated,
  DataHealthResponse,
  GenieAgent,
  GenieMessage,
  GeoFeatureCollection,
  Health,
  MapMetricResponse,
  MessageFeedbackRequest,
  MessageFeedbackResponse,
  MessageCreated,
  Neighborhood,
  NeighborhoodPulse,
  PipelineRunResponse,
  WakeRuntimeResponse,
} from "./types";
import { apiUrl } from "../config/runtime";

export class ApiError extends Error {
  status: number;
  code?: string;
  wakeAvailable?: boolean;

  constructor(
    message: string,
    status: number,
    code?: string,
    wakeAvailable?: boolean,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.wakeAvailable = wakeAvailable;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(apiUrl(path), {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Network error. Check your connection and retry.", 0);
  }
  if (!resp.ok) {
    let detail = `Request failed (${resp.status}).`;
    let code: string | undefined;
    let wakeAvailable: boolean | undefined;
    try {
      const body = (await resp.json()) as Record<string, unknown>;
      if (typeof body.detail === "string") detail = body.detail;
      else if (typeof body.error === "string") detail = body.error;
      if (typeof body.code === "string") code = body.code;
      if (typeof body.wake_available === "boolean") {
        wakeAvailable = body.wake_available;
      }
    } catch {
      /* keep default */
    }
    throw new ApiError(detail, resp.status, code, wakeAvailable);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  health: (init?: RequestInit) => request<Health>("/api/health", init),

  wakeRuntime: () =>
    request<WakeRuntimeResponse>("/api/runtime/wake", { method: "POST" }),

  genieAgent: () => request<GenieAgent>("/api/genie-agent"),

  startConversation: (question: string) =>
    request<ConversationCreated>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  followUp: (conversationId: string, question: string) =>
    request<MessageCreated>(
      `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
      { method: "POST", body: JSON.stringify({ question }) },
    ),

  getMessage: (conversationId: string, messageId: string) =>
    request<GenieMessage>(
      `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    ),

  sendMessageFeedback: (
    conversationId: string,
    messageId: string,
    feedback: MessageFeedbackRequest,
  ) =>
    request<MessageFeedbackResponse>(
      `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/feedback`,
      { method: "POST", body: JSON.stringify(feedback) },
    ),

  neighborhoods: () => request<Neighborhood[]>("/api/neighborhoods"),

  neighborhoodsGeo: () =>
    request<GeoFeatureCollection>("/api/neighborhoods/geo"),

  neighborhoodsMap: () =>
    request<MapMetricResponse>("/api/neighborhoods/map"),

  pulse: (communityArea: number) =>
    request<NeighborhoodPulse>(`/api/neighborhoods/${communityArea}/pulse`),

  compare: (areas: number[]) =>
    request<ComparisonResponse>(
      `/api/neighborhoods/compare?areas=${areas.join(",")}`,
    ),

  dataHealth: () => request<DataHealthResponse>("/api/data-health"),

  triggerPipeline: () =>
    request<PipelineRunResponse>("/api/data-health/pipeline-runs", {
      method: "POST",
    }),

  pipelineRun: (runId: number) =>
    request<PipelineRunResponse>(`/api/data-health/pipeline-runs/${runId}`),
};
