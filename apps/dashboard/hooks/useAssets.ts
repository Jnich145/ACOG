"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { Asset } from "@/lib/types";

/**
 * Hook to fetch assets for an episode
 */
export function useAssets(episodeId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Asset[]>(
    episodeId ? `/assets/episode/${episodeId}` : null,
    swrFetcher,
    {
      revalidateOnFocus: true,
    }
  );

  return {
    assets: data,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}
