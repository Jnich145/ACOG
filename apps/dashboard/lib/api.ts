/**
 * API Client for ACOG Backend
 *
 * Provides typed fetch wrappers for all backend endpoints.
 * Base URL is configured via NEXT_PUBLIC_ACOG_API_URL environment variable.
 */

import type {
  ApiResponse,
  Channel,
  ChannelCreate,
  Episode,
  EpisodeCreate,
  Asset,
  Job,
  PipelineStatusResponse,
  PipelineTriggerResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_ACOG_API_URL || "http://localhost:8000/api/v1";

/**
 * Custom error class for API errors
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Generic fetch wrapper with error handling
 */
async function fetcher<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorMessage = `HTTP ${res.status}`;
    let details: Record<string, unknown> | undefined;

    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
      details = errorData;
    } catch {
      // Failed to parse error response
    }

    throw new ApiError(errorMessage, res.status, details);
  }

  return res.json();
}

/**
 * SWR-compatible fetcher that extracts data from ApiResponse
 */
export async function swrFetcher<T>(url: string): Promise<T> {
  const response = await fetcher<ApiResponse<T>>(url);
  return response.data;
}

/**
 * API client with typed methods for all endpoints
 */
export const api = {
  // =========================================================================
  // Channels
  // =========================================================================

  /**
   * List all channels
   */
  getChannels: () =>
    fetcher<ApiResponse<Channel[]>>("/channels"),

  /**
   * Get a single channel by ID
   */
  getChannel: (id: string) =>
    fetcher<ApiResponse<Channel>>(`/channels/${id}`),

  /**
   * Create a new channel
   */
  createChannel: (data: ChannelCreate) =>
    fetcher<ApiResponse<Channel>>("/channels", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /**
   * Get all episodes for a channel
   */
  getChannelEpisodes: (channelId: string) =>
    fetcher<ApiResponse<Episode[]>>(`/channels/${channelId}/episodes`),

  // =========================================================================
  // Episodes
  // =========================================================================

  /**
   * Get a single episode by ID
   */
  getEpisode: (id: string) =>
    fetcher<ApiResponse<Episode>>(`/episodes/${id}`),

  /**
   * Create a new episode for a channel
   */
  createEpisode: (channelId: string, data: EpisodeCreate) =>
    fetcher<ApiResponse<Episode>>(`/episodes?channel_id=${channelId}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /**
   * List episodes with optional filters
   */
  getEpisodes: (params?: { channel_id?: string; status?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.channel_id) searchParams.set("channel_id", params.channel_id);
    if (params?.status) searchParams.set("status", params.status);
    const queryString = searchParams.toString();
    return fetcher<ApiResponse<Episode[]>>(
      `/episodes${queryString ? `?${queryString}` : ""}`
    );
  },

  // =========================================================================
  // Assets
  // =========================================================================

  /**
   * Get all assets for an episode
   * Note: The endpoint path is /assets/episode/{id}, not /episodes/{id}/assets
   */
  getEpisodeAssets: (episodeId: string) =>
    fetcher<ApiResponse<Asset[]>>(`/assets/episode/${episodeId}`),

  /**
   * Get a single asset by ID
   */
  getAsset: (id: string) =>
    fetcher<ApiResponse<Asset>>(`/assets/${id}`),

  // =========================================================================
  // Pipeline
  // =========================================================================

  /**
   * Run Stage 1 pipeline (planning -> scripting -> metadata)
   */
  runStage1: (episodeId: string) =>
    fetcher<ApiResponse<PipelineTriggerResponse>>(
      `/pipeline/episodes/${episodeId}/run-stage-1`,
      { method: "POST" }
    ),

  /**
   * Run full pipeline (all stages)
   */
  runFullPipeline: (episodeId: string) =>
    fetcher<ApiResponse<PipelineTriggerResponse>>(
      `/pipeline/episodes/${episodeId}/run-full`,
      { method: "POST" }
    ),

  /**
   * Get detailed pipeline status for an episode
   */
  getPipelineStatus: (episodeId: string) =>
    fetcher<ApiResponse<PipelineStatusResponse>>(
      `/pipeline/episodes/${episodeId}/status`
    ),

  /**
   * Trigger a specific pipeline stage
   */
  triggerStage: (
    episodeId: string,
    stage: string,
    params?: Record<string, unknown>,
    force?: boolean
  ) =>
    fetcher<ApiResponse<PipelineTriggerResponse>>(
      `/pipeline/episodes/${episodeId}/trigger`,
      {
        method: "POST",
        body: JSON.stringify({ stage, params: params || {}, force: force || false }),
      }
    ),

  /**
   * Advance to the next pipeline stage
   */
  advancePipeline: (episodeId: string) =>
    fetcher<ApiResponse<PipelineTriggerResponse>>(
      `/pipeline/episodes/${episodeId}/advance`,
      { method: "POST" }
    ),

  /**
   * Cancel all active jobs for an episode
   * Useful when jobs get stuck and need to be cleared before retrying
   */
  cancelEpisodeJobs: (episodeId: string) =>
    fetcher<ApiResponse<{ cancelled_count: number; cancelled_job_ids: string[]; message: string }>>(
      `/pipeline/episodes/${episodeId}/cancel-jobs`,
      { method: "POST" }
    ),

  /**
   * Cancel all stale jobs system-wide
   * Jobs older than max_age_minutes (default 30) are cancelled
   */
  cancelStaleJobs: (maxAgeMinutes: number = 30) =>
    fetcher<ApiResponse<{ cancelled_count: number; threshold_minutes: number; cancelled_jobs: Array<{ job_id: string; episode_id: string; stage: string; age_minutes: number }>; message: string }>>(
      `/pipeline/cancel-stale-jobs?max_age_minutes=${maxAgeMinutes}`,
      { method: "POST" }
    ),

  /**
   * Retry a specific stage and continue pipeline
   * Uses run-from-stage endpoint to re-run the failed stage and continue
   * through remaining stages automatically.
   */
  retryStage: (episodeId: string, stage: string) =>
    fetcher<ApiResponse<PipelineTriggerResponse>>(
      `/pipeline/episodes/${episodeId}/run-from-stage`,
      {
        method: "POST",
        body: JSON.stringify({ start_stage: stage, skip_stages: [] }),
      }
    ),

  /**
   * Run a single stage only (without continuing the pipeline)
   * Useful for manual step-by-step execution or testing.
   */
  triggerSingleStage: (
    episodeId: string,
    stage: string,
    params?: Record<string, unknown>,
    force?: boolean
  ) =>
    fetcher<ApiResponse<PipelineTriggerResponse>>(
      `/pipeline/episodes/${episodeId}/trigger`,
      {
        method: "POST",
        body: JSON.stringify({ stage, params: params || {}, force: force || false }),
      }
    ),

  // =========================================================================
  // Jobs
  // =========================================================================

  /**
   * Get all jobs for an episode
   */
  getEpisodeJobs: (episodeId: string) =>
    fetcher<ApiResponse<Job[]>>(`/jobs/episode/${episodeId}`),

  /**
   * Get a single job by ID
   */
  getJob: (id: string) =>
    fetcher<ApiResponse<Job>>(`/jobs/${id}`),

  // =========================================================================
  // Health
  // =========================================================================

  /**
   * Check API health
   */
  getHealth: () =>
    fetcher<{ status: string; version?: string }>("/health"),
};

/**
 * Helper to extract data from ApiResponse
 */
export function extractData<T>(response: ApiResponse<T>): T {
  return response.data;
}

/**
 * Helper to check if an error is an ApiError
 */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
