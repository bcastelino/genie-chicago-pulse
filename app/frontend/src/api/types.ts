// Mirrors the normalized server contracts in app/server/models.py.

export interface Health {
  status: string;
  mock_mode: boolean;
  environment: string;
  version: string;
}

export type MessageStatus =
  | "IN_PROGRESS"
  | "COMPLETED"
  | "EMPTY"
  | "FAILED"
  | "CANCELLED"
  | "EXPIRED";

export interface Column {
  name: string;
  type: string;
}

export interface QueryResult {
  columns: Column[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
}

export interface Provenance {
  conversation_id: string | null;
  message_id: string | null;
  attachment_id: string | null;
  statement_id: string | null;
  space_id: string | null;
}

export interface GenieMessage {
  conversation_id: string;
  message_id: string;
  status: MessageStatus;
  answer_text: string | null;
  sql: string | null;
  query_description: string | null;
  result: QueryResult | null;
  suggested_follow_ups: string[];
  is_empty: boolean;
  error: string | null;
  provenance: Provenance;
}

export interface GenieAgent {
  space_id: string;
  title: string;
  description: string;
  warehouse_id: string | null;
  updated_at: string | null;
  space_url: string | null;
}

export interface ConversationCreated {
  conversation_id: string;
  message_id: string;
  status: MessageStatus;
}

export interface MessageCreated {
  conversation_id: string;
  message_id: string;
  status: MessageStatus;
}

export type FeedbackRating = "POSITIVE" | "NEGATIVE" | "NONE";

export type FeedbackReason =
  | "INCORRECT_DATA"
  | "MISUNDERSTOOD_QUESTION"
  | "WRONG_TIME_OR_SCOPE"
  | "POOR_VISUALIZATION"
  | "OTHER";

export interface MessageFeedbackRequest {
  rating: FeedbackRating;
  reason: FeedbackReason | null;
  comment: string | null;
}

export interface MessageFeedbackResponse {
  rating: FeedbackRating;
}

export interface Neighborhood {
  community_area: number;
  community_area_name: string;
}

export interface MetricValue {
  key: string;
  label: string;
  value: number | null;
  previous_value: number | null;
  mom_change_pct: number | null;
  unit: string | null;
  available: boolean;
}

export interface TrendPoint {
  metric_month: string;
  value: number | null;
}

export interface CategoryCount {
  category: string;
  value: number;
}

export interface NeighborhoodPulse {
  community_area: number;
  community_area_name: string;
  metric_month: string | null;
  reporting_period_label: string | null;
  metrics: MetricValue[];
  trend_311: TrendPoint[];
  top_service_types: CategoryCount[];
}

export interface ComparisonResponse {
  metric_month: string | null;
  reporting_period_label: string | null;
  metric_keys: MetricValue[];
  neighborhoods: NeighborhoodPulse[];
}

export interface MapMetricPoint {
  community_area: number;
  community_area_name: string;
  value: number | null;
}

export interface MapMetricResponse {
  metric_month: string | null;
  reporting_period_label: string | null;
  metric_label: string;
  values: MapMetricPoint[];
}

export interface DatasetHealth {
  dataset: string;
  socrata_id: string | null;
  category: string | null;
  source_url: string | null;
  usage_status: "in_use" | "future_scope";
  row_count: number | null;
  min_date: string | null;
  max_date: string | null;
  last_ingested_at: string | null;
}

export interface DataHealthResponse {
  last_refresh_at: string | null;
  latest_reporting_month: string | null;
  pipeline_status: string;
  datasets: DatasetHealth[];
  metric_explanation: string;
  source_notice: string;
}

export interface PipelineTaskResponse {
  task_key: string;
  label: string;
  life_cycle_state: string;
  result_state: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_ms: number | null;
}

export interface PipelineRunResponse {
  run_id: number;
  life_cycle_state: string;
  result_state: string | null;
  run_page_url: string | null;
  started_new: boolean;
  start_time: string | null;
  end_time: string | null;
  duration_ms: number | null;
  tasks: PipelineTaskResponse[];
}

export interface GeoFeature {
  type: "Feature";
  properties: { community_area: number; community_area_name: string };
  geometry: unknown;
}

export interface GeoFeatureCollection {
  type: "FeatureCollection";
  features: GeoFeature[];
}
