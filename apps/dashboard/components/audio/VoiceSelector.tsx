"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Spinner, LoadingScreen } from "@/components/ui/Spinner";
import { useVoices } from "@/hooks/useVoices";
import { api } from "@/lib/api";
import type { Voice, VoiceSettings } from "@/lib/types";

// ============================================================================
// Types
// ============================================================================

export interface VoiceSelectorProps {
  /** Currently selected voice ID */
  selectedVoiceId?: string;
  /** Callback when user confirms voice selection */
  onSelect: (voiceId: string, settings: VoiceSettings, voiceName: string) => void;
  /** Whether to show voice settings sliders (default: true) */
  showSettings?: boolean;
  /** Optional className for the container */
  className?: string;
}

interface AudioPlayerState {
  isPlaying: boolean;
  isLoading: boolean;
  currentVoiceId: string | null;
  error: string | null;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_SETTINGS: VoiceSettings = {
  stability: 0.5,
  similarity_boost: 0.75,
  style: 0.0,
  use_speaker_boost: true,
};

const DEFAULT_PREVIEW_TEXT = "Hello! This is a preview of how this voice sounds. How does it sound to you?";

const CATEGORY_LABELS: Record<string, string> = {
  premade: "Premade",
  cloned: "Cloned",
  generated: "Generated",
  professional: "Professional",
};

// ============================================================================
// Helper Components
// ============================================================================

interface SliderControlProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  hint?: string;
}

function SliderControl({
  label,
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.01,
  hint,
}: SliderControlProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-700">{label}</label>
        <span className="text-sm text-gray-500 font-mono">{value.toFixed(2)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
      />
      {hint && <p className="text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

interface VoiceCardProps {
  voice: Voice;
  isSelected: boolean;
  isPlaying: boolean;
  isLoading: boolean;
  onSelect: () => void;
  onPlay: () => void;
  onStop: () => void;
}

function VoiceCard({
  voice,
  isSelected,
  isPlaying,
  isLoading,
  onSelect,
  onPlay,
  onStop,
}: VoiceCardProps) {
  const labels = voice.labels || {};
  const labelEntries = Object.entries(labels).filter(
    ([key]) => ["accent", "gender", "age", "description", "use_case"].includes(key)
  );

  return (
    <div
      className={cn(
        "p-4 rounded-lg border-2 transition-all cursor-pointer",
        isSelected
          ? "border-primary-500 bg-primary-50"
          : "border-gray-200 hover:border-gray-300 bg-white"
      )}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      aria-selected={isSelected}
      aria-label={`Voice: ${voice.name}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-gray-900 truncate">{voice.name}</h3>
            {voice.category && (
              <Badge variant="secondary" size="sm">
                {CATEGORY_LABELS[voice.category] || voice.category}
              </Badge>
            )}
          </div>

          {voice.description && (
            <p className="text-sm text-gray-600 mb-2 line-clamp-2">{voice.description}</p>
          )}

          {labelEntries.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {labelEntries.map(([key, value]) => (
                <span
                  key={key}
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                >
                  {key}: {value}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Play/Stop button for voice preview */}
          {voice.preview_url && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (isPlaying) {
                  onStop();
                } else {
                  onPlay();
                }
              }}
              disabled={isLoading}
              className={cn(
                "p-2 rounded-full transition-colors",
                isPlaying
                  ? "bg-primary-600 text-white hover:bg-primary-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              )}
              aria-label={isPlaying ? "Stop preview" : "Play preview"}
            >
              {isLoading ? (
                <Spinner size="sm" />
              ) : isPlaying ? (
                <StopIcon className="w-4 h-4" />
              ) : (
                <PlayIcon className="w-4 h-4" />
              )}
            </button>
          )}

          {/* Selection indicator */}
          {isSelected && (
            <div className="w-5 h-5 rounded-full bg-primary-600 flex items-center justify-center">
              <CheckIcon className="w-3 h-3 text-white" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Icons
// ============================================================================

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function StopIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function VoiceSelector({
  selectedVoiceId,
  onSelect,
  showSettings = true,
  className,
}: VoiceSelectorProps) {
  // Fetch voices
  const { voices, isLoading: isLoadingVoices, isError, error } = useVoices();

  // Local state
  const [selectedVoice, setSelectedVoice] = useState<Voice | null>(null);
  const [settings, setSettings] = useState<VoiceSettings>(DEFAULT_SETTINGS);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [previewText, setPreviewText] = useState(DEFAULT_PREVIEW_TEXT);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Audio player state
  const [audioState, setAudioState] = useState<AudioPlayerState>({
    isPlaying: false,
    isLoading: false,
    currentVoiceId: null,
    error: null,
  });

  // Audio element ref
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const customPreviewAudioRef = useRef<HTMLAudioElement | null>(null);

  // Initialize selected voice from prop
  useEffect(() => {
    if (selectedVoiceId && voices.length > 0) {
      const voice = voices.find((v) => v.voice_id === selectedVoiceId);
      if (voice) {
        setSelectedVoice(voice);
        // Initialize settings from voice if available
        if (voice.settings) {
          setSettings({
            stability: voice.settings.stability ?? DEFAULT_SETTINGS.stability,
            similarity_boost: voice.settings.similarity_boost ?? DEFAULT_SETTINGS.similarity_boost,
            style: voice.settings.style ?? DEFAULT_SETTINGS.style,
            use_speaker_boost: voice.settings.use_speaker_boost ?? DEFAULT_SETTINGS.use_speaker_boost,
          });
        }
      }
    }
  }, [selectedVoiceId, voices]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
      }
      if (customPreviewAudioRef.current) {
        customPreviewAudioRef.current.pause();
        customPreviewAudioRef.current.src = "";
      }
    };
  }, []);

  // Filter voices based on search and category
  const filteredVoices = voices.filter((voice) => {
    const matchesSearch =
      searchQuery === "" ||
      voice.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (voice.description?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false) ||
      Object.values(voice.labels || {}).some((label) =>
        label.toLowerCase().includes(searchQuery.toLowerCase())
      );

    const matchesCategory =
      categoryFilter === "all" || voice.category === categoryFilter;

    return matchesSearch && matchesCategory;
  });

  // Get unique categories
  const categories = Array.from(new Set(voices.map((v) => v.category).filter(Boolean)));

  // Play voice preview from preview_url
  const playPreview = useCallback((voice: Voice) => {
    if (!voice.preview_url) return;

    // Stop any current playback
    if (audioRef.current) {
      audioRef.current.pause();
    }

    setAudioState({
      isPlaying: false,
      isLoading: true,
      currentVoiceId: voice.voice_id,
      error: null,
    });

    // Create or reuse audio element
    if (!audioRef.current) {
      audioRef.current = new Audio();
    }

    const audio = audioRef.current;
    audio.src = voice.preview_url;

    audio.oncanplaythrough = () => {
      setAudioState((prev) => ({ ...prev, isLoading: false, isPlaying: true }));
      audio.play().catch((err) => {
        setAudioState({
          isPlaying: false,
          isLoading: false,
          currentVoiceId: null,
          error: err.message,
        });
      });
    };

    audio.onended = () => {
      setAudioState({
        isPlaying: false,
        isLoading: false,
        currentVoiceId: null,
        error: null,
      });
    };

    audio.onerror = () => {
      setAudioState({
        isPlaying: false,
        isLoading: false,
        currentVoiceId: null,
        error: "Failed to load audio preview",
      });
    };

    audio.load();
  }, []);

  // Stop current playback
  const stopPreview = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setAudioState({
      isPlaying: false,
      isLoading: false,
      currentVoiceId: null,
      error: null,
    });
  }, []);

  // Generate custom text preview with current settings
  const generateCustomPreview = useCallback(async () => {
    if (!selectedVoice || !previewText.trim()) return;

    setIsGeneratingPreview(true);
    setPreviewError(null);

    // Stop any current playback
    if (customPreviewAudioRef.current) {
      customPreviewAudioRef.current.pause();
    }

    try {
      // Get the streaming URL for the preview
      const streamUrl = api.getAudioPreviewStreamUrl({
        text: previewText,
        voice_id: selectedVoice.voice_id,
        stability: settings.stability,
        similarity_boost: settings.similarity_boost,
        style: settings.style,
      });

      // Create or reuse audio element
      if (!customPreviewAudioRef.current) {
        customPreviewAudioRef.current = new Audio();
      }

      const audio = customPreviewAudioRef.current;
      audio.src = streamUrl;

      audio.oncanplaythrough = () => {
        setIsGeneratingPreview(false);
        audio.play().catch((err) => {
          setPreviewError(err.message);
        });
      };

      audio.onended = () => {
        setIsGeneratingPreview(false);
      };

      audio.onerror = () => {
        setIsGeneratingPreview(false);
        setPreviewError("Failed to generate audio preview. Please check your connection and try again.");
      };

      audio.load();
    } catch (err) {
      setIsGeneratingPreview(false);
      setPreviewError(
        err instanceof Error ? err.message : "Failed to generate preview"
      );
    }
  }, [selectedVoice, previewText, settings]);

  // Handle voice selection
  const handleVoiceSelect = useCallback((voice: Voice) => {
    setSelectedVoice(voice);
    // Initialize settings from voice defaults if available
    if (voice.settings) {
      setSettings({
        stability: voice.settings.stability ?? DEFAULT_SETTINGS.stability,
        similarity_boost: voice.settings.similarity_boost ?? DEFAULT_SETTINGS.similarity_boost,
        style: voice.settings.style ?? DEFAULT_SETTINGS.style,
        use_speaker_boost: voice.settings.use_speaker_boost ?? DEFAULT_SETTINGS.use_speaker_boost,
      });
    } else {
      setSettings(DEFAULT_SETTINGS);
    }
  }, []);

  // Handle confirm selection
  const handleConfirmSelection = useCallback(() => {
    if (selectedVoice) {
      onSelect(selectedVoice.voice_id, settings, selectedVoice.name);
    }
  }, [selectedVoice, settings, onSelect]);

  // Update individual settings
  const updateSetting = useCallback(
    (key: keyof VoiceSettings, value: number | boolean) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  // Loading state
  if (isLoadingVoices) {
    return (
      <Card className={className}>
        <CardContent>
          <LoadingScreen />
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card className={className}>
        <CardContent>
          <div className="text-center py-8">
            <p className="text-red-600 mb-2">Failed to load voices</p>
            <p className="text-sm text-gray-500">
              {error instanceof Error ? error.message : "Unknown error occurred"}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Voice List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Select a Voice</CardTitle>
          <span className="text-sm text-gray-500">{voices.length} voices available</span>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search and Filter */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search voices..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="all">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {CATEGORY_LABELS[cat] || cat}
                </option>
              ))}
            </select>
          </div>

          {/* Voice Grid */}
          <div className="grid gap-3 max-h-[400px] overflow-y-auto pr-1">
            {filteredVoices.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                No voices found matching your search criteria
              </div>
            ) : (
              filteredVoices.map((voice) => (
                <VoiceCard
                  key={voice.voice_id}
                  voice={voice}
                  isSelected={selectedVoice?.voice_id === voice.voice_id}
                  isPlaying={
                    audioState.isPlaying &&
                    audioState.currentVoiceId === voice.voice_id
                  }
                  isLoading={
                    audioState.isLoading &&
                    audioState.currentVoiceId === voice.voice_id
                  }
                  onSelect={() => handleVoiceSelect(voice)}
                  onPlay={() => playPreview(voice)}
                  onStop={stopPreview}
                />
              ))
            )}
          </div>

          {/* Audio error display */}
          {audioState.error && (
            <p className="text-sm text-red-600">{audioState.error}</p>
          )}
        </CardContent>
      </Card>

      {/* Voice Settings (shown when a voice is selected and showSettings is true) */}
      {selectedVoice && showSettings && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Voice Settings</CardTitle>
            <Badge variant="info">{selectedVoice.name}</Badge>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Settings Sliders */}
            <div className="space-y-4">
              <SliderControl
                label="Stability"
                value={settings.stability}
                onChange={(v) => updateSetting("stability", v)}
                hint="Higher values produce more consistent speech, lower values are more expressive"
              />
              <SliderControl
                label="Similarity Boost"
                value={settings.similarity_boost}
                onChange={(v) => updateSetting("similarity_boost", v)}
                hint="Higher values make the voice more similar to the original"
              />
              <SliderControl
                label="Style"
                value={settings.style}
                onChange={(v) => updateSetting("style", v)}
                hint="Exaggerates the speaking style (use sparingly, increases latency)"
              />
            </div>

            {/* Custom Preview */}
            <div className="pt-4 border-t border-gray-100 space-y-3">
              <h4 className="text-sm font-medium text-gray-700">Custom Preview</h4>
              <Textarea
                value={previewText}
                onChange={(e) => setPreviewText(e.target.value)}
                placeholder="Enter text to preview..."
                rows={3}
                hint="Enter custom text to preview with the current voice settings"
              />
              <div className="flex items-center gap-3">
                <Button
                  variant="secondary"
                  onClick={generateCustomPreview}
                  loading={isGeneratingPreview}
                  disabled={!previewText.trim()}
                  leftIcon={<PlayIcon className="w-4 h-4" />}
                >
                  Generate Preview
                </Button>
                {previewError && (
                  <span className="text-sm text-red-600">{previewError}</span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirm Selection Button */}
      {selectedVoice && (
        <div className="flex justify-end">
          <Button onClick={handleConfirmSelection}>
            Confirm Voice Selection
          </Button>
        </div>
      )}
    </div>
  );
}
