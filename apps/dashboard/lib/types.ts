/**
 * TypeScript type definitions for ACOG Dashboard
 *
 * These types align with the FastAPI backend schemas defined in:
 * - apps/api/src/acog/schemas/channel.py
 * - apps/api/src/acog/schemas/episode.py
 * - apps/api/src/acog/schemas/asset.py
 * - apps/api/src/acog/schemas/job.py
 * - apps/api/src/acog/models/enums.py
 */

// ============================================================================
// Enums
// ============================================================================

export type EpisodeStatus =
  | "idea"
  | "planning"
  | "scripting"
  | "script_review"
  | "audio"
  | "avatar"
  | "broll"
  | "assembly"
  | "ready"
  | "publishing"
  | "published"
  | "failed"
  | "cancelled";

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type AssetType =
  | "script"
  | "audio"
  | "avatar_video"
  | "b_roll"
  | "assembled_video"
  | "thumbnail"
  | "plan"
  | "metadata";

export type Priority = "low" | "normal" | "high" | "urgent";

export type IdeaSource = "manual" | "pulse" | "series" | "followup" | "repurpose";

export type StageStatusType = "pending" | "queued" | "processing" | "completed" | "failed" | "skipped";

// ============================================================================
// API Response Wrapper
// ============================================================================

export interface ApiResponse<T> {
  data: T;
  meta: Record<string, unknown>;
}

export interface PaginationMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

// ============================================================================
// Channel Types
// ============================================================================

export interface Persona {
  name: string;
  background: string;
  voice?: string;
  values?: string[];
  expertise?: string[];
}

export interface StyleGuide {
  tone?: string;
  complexity?: string;
  pacing?: string;
  humor_level?: string;
  video_length_target?: {
    min_minutes: number;
    max_minutes: number;
  };
  do_rules?: string[];
  dont_rules?: string[];
}

export interface VoiceProfile {
  provider: string;
  voice_id?: string;
  stability?: number;
  similarity_boost?: number;
  style?: number;
}

export interface AvatarProfile {
  provider: string;
  avatar_id?: string;
  background?: string;
  framing?: string;
  attire?: string;
}

export interface Channel {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  niche: string | null;
  persona: Record<string, unknown>;
  style_guide: Record<string, unknown>;
  voice_profile: Record<string, unknown>;
  avatar_profile: Record<string, unknown>;
  cadence: string | null;
  platform_config: Record<string, unknown>;
  youtube_channel_id: string | null;
  is_active: boolean;
  episode_count: number;
  stats?: ChannelStats | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface ChannelStats {
  total_episodes: number;
  published_episodes: number;
  failed_episodes: number;
  in_progress_episodes: number;
  avg_production_time_minutes: number | null;
}

export interface ChannelCreate {
  name: string;
  description?: string;
  niche?: string;
  persona: Persona;
  style_guide?: StyleGuide;
  voice_profile?: VoiceProfile;
  avatar_profile?: AvatarProfile;
  youtube_channel_id?: string;
  is_active?: boolean;
}

// ============================================================================
// Episode Types
// ============================================================================

export interface ScriptSegment {
  type: string;
  start_time: number;
  end_time: number;
  text: string;
  tone?: string;
  notes?: string;
  broll_cue?: string;
}

export interface ScriptContent {
  version: number;
  status: string;
  full_text: string | null;
  segments?: ScriptSegment[];
  word_count: number;
  estimated_duration_seconds: number;
  generated_at?: string;
  model_used?: string;
}

export interface StageStatus {
  status: StageStatusType;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  error: string | null;
  retry_count?: number;
  output_ref?: string | null;
}

export interface PipelineState {
  current_stage: string;
  overall_status: string;
  stages: Record<string, StageStatus>;
}

export interface CostTracking {
  estimated_cost_usd: number | null;
  actual_cost_usd: number;
  breakdown: Record<string, number>;
}

export interface Episode {
  id: string;
  channel_id: string;
  title: string | null;
  slug: string | null;
  idea_brief: string | null;
  idea_source: IdeaSource;
  pulse_event_id?: string | null;
  status: EpisodeStatus;
  target_length_minutes?: number | null;
  priority: Priority;
  tags?: string[];
  notes?: string | null;
  auto_advance?: boolean;
  plan: Record<string, unknown> | null;
  script: ScriptContent | null;
  metadata: Record<string, unknown> | null;
  pipeline_state: PipelineState | null;
  cost_tracking?: CostTracking | null;
  asset_count: number;
  assets?: Asset[];
  published_url?: string | null;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

export interface EpisodeCreate {
  title: string;
  idea_brief?: string;
  idea_source?: IdeaSource;
  target_length_minutes?: number;
  priority?: Priority;
  tags?: string[];
  notes?: string;
  auto_advance?: boolean;
}

// ============================================================================
// Asset Types
// ============================================================================

export interface Asset {
  id: string;
  episode_id: string;
  type: AssetType;
  filename: string | null;
  uri: string;
  storage_bucket?: string | null;
  storage_key?: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  duration_seconds?: number | null;
  provider?: string | null;
  provider_job_id?: string | null;
  version?: number;
  metadata: Record<string, unknown>;
  checksum?: string | null;
  is_primary: boolean;
  created_at: string;
  updated_at?: string;
  deleted_at?: string | null;
}

// ============================================================================
// Job Types
// ============================================================================

export interface Job {
  id: string;
  episode_id: string;
  stage: string;
  status: JobStatus;
  celery_task_id?: string | null;
  input_params?: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  error_message: string | null;
  retry_count?: number;
  max_retries?: number;
  cost_usd?: number | null;
  tokens_used?: number | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  created_at?: string;
  updated_at?: string;
}

// ============================================================================
// Pipeline Types
// ============================================================================

export interface PipelineStageInfo {
  status: string;
  job_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  error: string | null;
  attempts: number;
}

export interface PipelineProgress {
  completed_stages: number;
  total_stages: number;
  percent_complete: number;
}

export interface ActiveJob {
  id: string;
  stage: string;
  status: string;
}

export interface PipelineStatusResponse {
  episode_id: string;
  episode_status: EpisodeStatus;
  pipeline_progress: PipelineProgress;
  stages: Record<string, PipelineStageInfo>;
  active_jobs: ActiveJob[];
}

export interface PipelineTriggerResponse {
  job_id: string;
  episode_id: string;
  stage: string;
  status: string;
  message: string;
}

// ============================================================================
// Helper Types
// ============================================================================

// Pipeline stage names for display
export const PIPELINE_STAGES = [
  "planning",
  "scripting",
  "script_review",
  "metadata",
  "audio",
  "avatar",
  "broll",
  "assembly",
  "upload",
] as const;

export type PipelineStageName = (typeof PIPELINE_STAGES)[number];

// Stage 1 pipeline stages (content generation only)
export const STAGE_1_STAGES = ["planning", "scripting", "metadata"] as const;

// Status display configuration
export const STATUS_CONFIG: Record<
  EpisodeStatus,
  { label: string; color: string; bgColor: string }
> = {
  idea: { label: "Idea", color: "text-gray-700", bgColor: "bg-gray-100" },
  planning: { label: "Planning", color: "text-blue-700", bgColor: "bg-blue-100" },
  scripting: { label: "Scripting", color: "text-blue-700", bgColor: "bg-blue-100" },
  script_review: { label: "Script Review", color: "text-yellow-700", bgColor: "bg-yellow-100" },
  audio: { label: "Audio", color: "text-purple-700", bgColor: "bg-purple-100" },
  avatar: { label: "Avatar", color: "text-purple-700", bgColor: "bg-purple-100" },
  broll: { label: "B-Roll", color: "text-purple-700", bgColor: "bg-purple-100" },
  assembly: { label: "Assembly", color: "text-indigo-700", bgColor: "bg-indigo-100" },
  ready: { label: "Ready", color: "text-green-700", bgColor: "bg-green-100" },
  publishing: { label: "Publishing", color: "text-orange-700", bgColor: "bg-orange-100" },
  published: { label: "Published", color: "text-green-700", bgColor: "bg-green-100" },
  failed: { label: "Failed", color: "text-red-700", bgColor: "bg-red-100" },
  cancelled: { label: "Cancelled", color: "text-gray-700", bgColor: "bg-gray-100" },
};

export const PRIORITY_CONFIG: Record<
  Priority,
  { label: string; color: string; bgColor: string }
> = {
  low: { label: "Low", color: "text-gray-600", bgColor: "bg-gray-100" },
  normal: { label: "Normal", color: "text-blue-600", bgColor: "bg-blue-100" },
  high: { label: "High", color: "text-orange-600", bgColor: "bg-orange-100" },
  urgent: { label: "Urgent", color: "text-red-600", bgColor: "bg-red-100" },
};

export const STAGE_STATUS_CONFIG: Record<
  StageStatusType,
  { label: string; color: string; bgColor: string }
> = {
  pending: { label: "Pending", color: "text-gray-500", bgColor: "bg-gray-100" },
  queued: { label: "Queued", color: "text-yellow-600", bgColor: "bg-yellow-100" },
  processing: { label: "Processing", color: "text-blue-600", bgColor: "bg-blue-100" },
  completed: { label: "Completed", color: "text-green-600", bgColor: "bg-green-100" },
  failed: { label: "Failed", color: "text-red-600", bgColor: "bg-red-100" },
  skipped: { label: "Skipped", color: "text-gray-500", bgColor: "bg-gray-100" },
};
