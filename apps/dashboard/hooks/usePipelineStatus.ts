"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { PipelineStatusResponse } from "@/lib/types";

/**
 * Hook to fetch pipeline status for an episode
 * Supports polling when pipeline is running
 */
export function usePipelineStatus(
  episodeId: string | null,
  shouldPoll: boolean = false
) {
  const { data, error, isLoading, mutate } = useSWR<PipelineStatusResponse>(
    episodeId ? `/pipeline/episodes/${episodeId}/status` : null,
    swrFetcher,
    {
      refreshInterval: shouldPoll ? 3000 : 0, // Poll every 3s when running
      revalidateOnFocus: true,
      dedupingInterval: 1000,
    }
  );

  // Determine if pipeline is currently running
  const isRunning = data?.active_jobs && data.active_jobs.length > 0;

  return {
    status: data,
    isLoading,
    isError: !!error,
    error,
    isRunning,
    mutate,
  };
}
