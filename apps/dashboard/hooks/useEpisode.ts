"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { Episode } from "@/lib/types";

/**
 * Hook to fetch a single episode by ID
 */
export function useEpisode(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Episode>(
    id ? `/episodes/${id}` : null,
    swrFetcher,
    {
      revalidateOnFocus: true,
    }
  );

  return {
    episode: data,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}
