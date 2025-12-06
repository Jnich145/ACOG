"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { Channel, Episode } from "@/lib/types";

/**
 * Hook to fetch a single channel by ID
 */
export function useChannel(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Channel>(
    id ? `/channels/${id}` : null,
    swrFetcher,
    {
      revalidateOnFocus: true,
    }
  );

  return {
    channel: data,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}

/**
 * Hook to fetch episodes for a channel
 */
export function useChannelEpisodes(channelId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Episode[]>(
    channelId ? `/channels/${channelId}/episodes` : null,
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
