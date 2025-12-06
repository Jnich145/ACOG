"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { Job } from "@/lib/types";

/**
 * Hook to fetch jobs for an episode
 */
export function useJobs(episodeId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Job[]>(
    episodeId ? `/jobs/episode/${episodeId}` : null,
    swrFetcher,
    {
      revalidateOnFocus: true,
    }
  );

  return {
    jobs: data,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}
