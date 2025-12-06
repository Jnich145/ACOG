"use client";

import useSWR from "swr";
import { swrFetcher } from "@/lib/api";
import type { VoiceListResponse } from "@/lib/types";

/**
 * Hook to fetch all available voices from ElevenLabs
 */
export function useVoices(showLegacy: boolean = false) {
  const { data, error, isLoading, mutate } = useSWR<VoiceListResponse>(
    `/audio/voices${showLegacy ? "?show_legacy=true" : ""}`,
    swrFetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60000, // Voices don't change often, cache for 1 minute
    }
  );

  return {
    voices: data?.voices ?? [],
    total: data?.total ?? 0,
    isLoading,
    isError: !!error,
    error,
    mutate,
  };
}
