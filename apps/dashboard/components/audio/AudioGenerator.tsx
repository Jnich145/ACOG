"use client";

import { useState, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { api, isApiError } from "@/lib/api";
import type { VoiceSettings, AudioPreviewResponse, EpisodeAudioResponse } from "@/lib/types";

// ============================================================================
// Types
// ============================================================================

export interface AudioGeneratorProps {
  episodeId: string;
  selectedVoiceId: string | null;
  voiceName?: string;
  settings: VoiceSettings;
  hasScript: boolean;
  onAudioGenerated?: (response: EpisodeAudioResponse) => void;
  className?: string;
}

interface GenerationState {
  isGenerating: boolean;
  isPreviewGenerating: boolean;
  error: string | null;
  previewResponse: AudioPreviewResponse | null;
  fullAudioResponse: EpisodeAudioResponse | null;
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

function PauseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  );
}

function VolumeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

// ============================================================================
// Audio Player Sub-component
// ============================================================================

interface AudioPlayerProps {
  audioBase64: string;
  duration: number;
  label: string;
}

function AudioPlayer({ audioBase64, duration, label }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  const togglePlayback = useCallback(() => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  }, []);

  const handleEnded = useCallback(() => {
    setIsPlaying(false);
    setCurrentTime(0);
  }, []);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const handleSeek = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  }, []);

  const downloadAudio = useCallback(() => {
    const link = document.createElement("a");
    link.href = `data:audio/mpeg;base64,${audioBase64}`;
    link.download = `${label.toLowerCase().replace(/\s+/g, "-")}.mp3`;
    link.click();
  }, [audioBase64, label]);

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <audio
        ref={audioRef}
        src={`data:audio/mpeg;base64,${audioBase64}`}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
      />

      <div className="flex items-center gap-4">
        <button
          onClick={togglePlayback}
          className="p-3 rounded-full bg-primary-600 text-white hover:bg-primary-700 transition-colors"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? (
            <PauseIcon className="w-5 h-5" />
          ) : (
            <PlayIcon className="w-5 h-5" />
          )}
        </button>

        <div className="flex-1">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={duration}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
          />
        </div>

        <button
          onClick={downloadAudio}
          className="p-2 rounded-lg text-gray-600 hover:bg-gray-200 transition-colors"
          aria-label="Download"
          title="Download MP3"
        >
          <DownloadIcon className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function AudioGenerator({
  episodeId,
  selectedVoiceId,
  voiceName,
  settings,
  hasScript,
  onAudioGenerated,
  className,
}: AudioGeneratorProps) {
  const [state, setState] = useState<GenerationState>({
    isGenerating: false,
    isPreviewGenerating: false,
    error: null,
    previewResponse: null,
    fullAudioResponse: null,
  });

  // Generate preview (first 500 chars of script)
  const handleGeneratePreview = useCallback(async () => {
    if (!selectedVoiceId) return;

    setState((prev) => ({
      ...prev,
      isPreviewGenerating: true,
      error: null,
    }));

    try {
      const response = await api.previewEpisodeAudio(episodeId, {
        voice_id: selectedVoiceId,
        stability: settings.stability,
        similarity_boost: settings.similarity_boost,
        style: settings.style,
      });

      setState((prev) => ({
        ...prev,
        isPreviewGenerating: false,
        previewResponse: response.data,
      }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isPreviewGenerating: false,
        error: isApiError(err) ? err.message : "Failed to generate preview",
      }));
    }
  }, [episodeId, selectedVoiceId, settings]);

  // Generate full episode audio
  const handleGenerateFullAudio = useCallback(async () => {
    if (!selectedVoiceId) return;

    setState((prev) => ({
      ...prev,
      isGenerating: true,
      error: null,
    }));

    try {
      const response = await api.generateEpisodeAudio(episodeId, {
        voice_id: selectedVoiceId,
        stability: settings.stability,
        similarity_boost: settings.similarity_boost,
        style: settings.style,
        save_to_storage: true,
      });

      setState((prev) => ({
        ...prev,
        isGenerating: false,
        fullAudioResponse: response.data,
      }));

      if (onAudioGenerated) {
        onAudioGenerated(response.data);
      }
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isGenerating: false,
        error: isApiError(err) ? err.message : "Failed to generate audio",
      }));
    }
  }, [episodeId, selectedVoiceId, settings, onAudioGenerated]);

  const canGenerate = selectedVoiceId && hasScript;

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <VolumeIcon className="w-5 h-5" />
          Audio Generation
        </CardTitle>
        {selectedVoiceId && voiceName && (
          <Badge variant="info">{voiceName}</Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Requirements Check */}
        {!canGenerate && (
          <Alert variant="warning">
            {!hasScript && "No script available. Generate a script first."}
            {hasScript && !selectedVoiceId && "Select a voice above to generate audio."}
          </Alert>
        )}

        {/* Error Display */}
        {state.error && (
          <Alert
            variant="error"
            title="Generation Error"
            onDismiss={() => setState((prev) => ({ ...prev, error: null }))}
          >
            {state.error}
          </Alert>
        )}

        {/* Generation Buttons */}
        {canGenerate && (
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              variant="secondary"
              onClick={handleGeneratePreview}
              loading={state.isPreviewGenerating}
              disabled={state.isGenerating}
              leftIcon={<PlayIcon className="w-4 h-4" />}
            >
              Preview Audio (First 500 chars)
            </Button>
            <Button
              onClick={handleGenerateFullAudio}
              loading={state.isGenerating}
              disabled={state.isPreviewGenerating}
              leftIcon={<VolumeIcon className="w-4 h-4" />}
            >
              Generate Full Audio
            </Button>
          </div>
        )}

        {/* Voice Settings Summary */}
        {selectedVoiceId && (
          <div className="text-sm text-gray-500 bg-gray-50 rounded-lg p-3">
            <div className="font-medium text-gray-700 mb-2">Current Settings</div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <span className="text-gray-400">Stability:</span>{" "}
                <span className="font-mono">{settings.stability.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-gray-400">Similarity:</span>{" "}
                <span className="font-mono">{settings.similarity_boost.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-gray-400">Style:</span>{" "}
                <span className="font-mono">{settings.style.toFixed(2)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Preview Audio Player */}
        {state.previewResponse && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700">Preview Audio</h4>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>{state.previewResponse.character_count} chars</span>
                <span>•</span>
                <span>~${state.previewResponse.estimated_cost_usd.toFixed(4)}</span>
              </div>
            </div>
            <AudioPlayer
              audioBase64={state.previewResponse.audio_base64}
              duration={state.previewResponse.estimated_duration_seconds}
              label="preview-audio"
            />
          </div>
        )}

        {/* Full Audio Result */}
        {state.fullAudioResponse && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700">Generated Audio</h4>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>{state.fullAudioResponse.character_count} chars</span>
                <span>•</span>
                <span>{Math.round(state.fullAudioResponse.estimated_duration_seconds)}s</span>
                <span>•</span>
                <span>~${state.fullAudioResponse.estimated_cost_usd.toFixed(4)}</span>
              </div>
            </div>

            {state.fullAudioResponse.audio_base64 ? (
              <AudioPlayer
                audioBase64={state.fullAudioResponse.audio_base64}
                duration={state.fullAudioResponse.estimated_duration_seconds}
                label="episode-audio"
              />
            ) : state.fullAudioResponse.storage_uri ? (
              <Alert variant="success" title="Audio Saved">
                Audio has been saved to storage: {state.fullAudioResponse.storage_uri}
              </Alert>
            ) : null}
          </div>
        )}

        {/* Generation In Progress */}
        {state.isGenerating && (
          <div className="flex items-center justify-center py-8">
            <div className="text-center">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mx-auto mb-3"></div>
              <p className="text-sm text-gray-600">Generating full episode audio...</p>
              <p className="text-xs text-gray-400 mt-1">This may take a minute for longer scripts</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
