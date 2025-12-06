"use client";

import useSWR from "swr";
import { api, swrFetcher } from "@/lib/api";
import type { Channel } from "@/lib/types";

/**
 * Hook to fetch all channels
 */
export function useChannels() {
  const { data, error, isLoading, mutate } = useSWR<Channel[]>(
    "/channels",
    swrFetcher,
    {
      revalidateOnFocus: true,
      dedupingInterval: 5000,
    }
  );

  return {
    channels: data,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}
