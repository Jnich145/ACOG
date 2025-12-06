"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { Episode } from "@/lib/types";

interface UseEpisodesOptions {
  channelId?: string;
  status?: string;
}

/**
 * Hook to fetch episodes with optional filters
 */
export function useEpisodes(options: UseEpisodesOptions = {}) {
  const params = new URLSearchParams();
  if (options.channelId) params.set("channel_id", options.channelId);
  if (options.status) params.set("status", options.status);

  const queryString = params.toString();
  const key = `/episodes${queryString ? `?${queryString}` : ""}`;

  const { data, error, isLoading, mutate } = useSWR<Episode[]>(
    key,
    swrFetcher,
    {
      revalidateOnFocus: true,
      dedupingInterval: 3000,
    }
  );

  return {
    episodes: data,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}
