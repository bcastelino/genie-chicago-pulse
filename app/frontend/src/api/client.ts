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
} from "./types";
import { apiUrl } from "../config/runtime";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
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
    try {
      const body = await resp.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),

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
