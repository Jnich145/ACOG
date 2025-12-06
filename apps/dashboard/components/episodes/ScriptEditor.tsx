"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Alert } from "@/components/ui/Alert";
import { api, ApiError } from "@/lib/api";
import type { ScriptContent } from "@/lib/types";

// ============================================================================
// Types
// ============================================================================

interface ScriptEditorProps {
  episodeId: string;
  script: ScriptContent | null;
  onScriptUpdated: () => void;
}

interface ScriptVersion {
  version: number;
  word_count: number;
  estimated_duration_seconds: number;
  created_at: string;
  model_used: string;
}

interface PendingRevision {
  proposed_revision: string;
  original_script: string;
  revision_instructions: string;
  model_used: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (minutes === 0) return `${secs}s`;
  if (secs === 0) return `${minutes}m`;
  return `${minutes}m ${secs}s`;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function countWords(text: string): number {
  return text
    .trim()
    .split(/\s+/)
    .filter((word) => word.length > 0).length;
}

// ============================================================================
// Sub-Components
// ============================================================================

interface ScriptStatsProps {
  wordCount: number;
  estimatedDuration: number;
  modelUsed?: string;
  version?: number;
}

function ScriptStats({ wordCount, estimatedDuration, modelUsed, version }: ScriptStatsProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
      <div className="flex items-center gap-1.5">
        <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span>{wordCount.toLocaleString()} words</span>
      </div>
      <div className="flex items-center gap-1.5">
        <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>~{formatDuration(estimatedDuration)}</span>
      </div>
      {modelUsed && (
        <div className="flex items-center gap-1.5">
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span className="font-mono text-xs">{modelUsed}</span>
        </div>
      )}
      {version !== undefined && (
        <Badge variant="secondary" size="sm">
          v{version}
        </Badge>
      )}
    </div>
  );
}

interface RevisionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (instructions: string) => void;
  isLoading: boolean;
}

function RevisionModal({ isOpen, onClose, onSubmit, isLoading }: RevisionModalProps) {
  const [instructions, setInstructions] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (instructions.trim()) {
      onSubmit(instructions.trim());
    }
  };

  const handleClose = () => {
    setInstructions("");
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 transition-opacity"
        onClick={handleClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 z-10">
        <form onSubmit={handleSubmit}>
          <div className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              Request Script Revision
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Describe how you would like the script to be revised. Be specific about
              tone, length, content changes, or any other adjustments.
            </p>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g., Make the introduction more engaging, shorten the middle section, add more statistics..."
              className={cn(
                "w-full h-32 px-3 py-2 rounded-md border border-gray-300",
                "text-sm text-gray-900 placeholder-gray-400",
                "focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent",
                "resize-none"
              )}
              disabled={isLoading}
              autoFocus
            />
          </div>
          <div className="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 rounded-b-lg border-t border-gray-100">
            <Button
              type="button"
              variant="ghost"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={isLoading}
              disabled={!instructions.trim() || isLoading}
            >
              Generate Revision
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface DiffViewProps {
  original: string;
  revised: string;
}

function DiffView({ original, revised }: DiffViewProps) {
  const originalWordCount = countWords(original);
  const revisedWordCount = countWords(revised);
  const wordDiff = revisedWordCount - originalWordCount;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Original Script */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium text-gray-700">Original Script</h4>
          <span className="text-xs text-gray-500">{originalWordCount} words</span>
        </div>
        <div className="h-[400px] overflow-y-auto rounded-md border border-gray-200 bg-gray-50 p-4">
          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {original}
          </p>
        </div>
      </div>

      {/* Revised Script */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-medium text-gray-700">Proposed Revision</h4>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{revisedWordCount} words</span>
            {wordDiff !== 0 && (
              <Badge
                variant={wordDiff > 0 ? "info" : "warning"}
                size="sm"
              >
                {wordDiff > 0 ? "+" : ""}{wordDiff}
              </Badge>
            )}
          </div>
        </div>
        <div className="h-[400px] overflow-y-auto rounded-md border border-primary-200 bg-primary-50 p-4">
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
            {revised}
          </p>
        </div>
      </div>
    </div>
  );
}

interface VersionHistoryProps {
  versions: ScriptVersion[];
  currentVersion: number;
  onRestore: (version: number) => void;
  isRestoring: boolean;
  restoringVersion: number | null;
}

function VersionHistory({
  versions,
  currentVersion,
  onRestore,
  isRestoring,
  restoringVersion
}: VersionHistoryProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (versions.length === 0) {
    return null;
  }

  return (
    <Card variant="outline" padding="none">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-medium text-gray-700">Version History</span>
          <Badge variant="default" size="sm">
            {versions.length} version{versions.length !== 1 ? "s" : ""}
          </Badge>
        </div>
        <svg
          className={cn(
            "w-4 h-4 text-gray-400 transition-transform",
            isExpanded && "rotate-180"
          )}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="border-t border-gray-100">
          <div className="divide-y divide-gray-100">
            {versions.map((version) => (
              <div
                key={version.version}
                className={cn(
                  "px-4 py-3 flex items-center justify-between",
                  version.version === currentVersion && "bg-primary-50"
                )}
              >
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={version.version === currentVersion ? "info" : "default"}
                      size="sm"
                    >
                      v{version.version}
                    </Badge>
                    {version.version === currentVersion && (
                      <span className="text-xs text-primary-600 font-medium">Current</span>
                    )}
                  </div>
                  <div className="text-sm text-gray-600">
                    <span>{version.word_count} words</span>
                    <span className="mx-2 text-gray-300">|</span>
                    <span>~{formatDuration(version.estimated_duration_seconds)}</span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatDate(version.created_at)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 font-mono">
                    {version.model_used}
                  </span>
                  {version.version !== currentVersion && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRestore(version.version)}
                      loading={isRestoring && restoringVersion === version.version}
                      disabled={isRestoring}
                    >
                      Restore
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function ScriptEditor({ episodeId, script, onScriptUpdated }: ScriptEditorProps) {
  // UI State
  const [isRevisionModalOpen, setIsRevisionModalOpen] = useState(false);
  const [isVersionHistoryLoaded, setIsVersionHistoryLoaded] = useState(false);

  // Loading States
  const [isRequestingRevision, setIsRequestingRevision] = useState(false);
  const [isAcceptingRevision, setIsAcceptingRevision] = useState(false);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [isRestoringVersion, setIsRestoringVersion] = useState(false);
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null);

  // Data State
  const [pendingRevision, setPendingRevision] = useState<PendingRevision | null>(null);
  const [versions, setVersions] = useState<ScriptVersion[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Check if there's a pending revision based on script metadata
  const hasPendingRevision = script?.status === "pending_revision" || pendingRevision !== null;

  // Load version history
  const loadVersionHistory = useCallback(async () => {
    if (isVersionHistoryLoaded || isLoadingVersions) return;

    setIsLoadingVersions(true);
    setError(null);

    try {
      const response = await api.getScriptVersions(episodeId);
      setVersions(response.data);
      setIsVersionHistoryLoaded(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to load version history: ${err.message}`);
      } else {
        setError("Failed to load version history");
      }
    } finally {
      setIsLoadingVersions(false);
    }
  }, [episodeId, isVersionHistoryLoaded, isLoadingVersions]);

  // Request revision
  const handleRequestRevision = async (instructions: string) => {
    setIsRequestingRevision(true);
    setError(null);

    try {
      const response = await api.reviseScript(episodeId, instructions);
      setPendingRevision(response.data);
      setIsRevisionModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to generate revision: ${err.message}`);
      } else {
        setError("Failed to generate revision");
      }
    } finally {
      setIsRequestingRevision(false);
    }
  };

  // Accept revision
  const handleAcceptRevision = async () => {
    setIsAcceptingRevision(true);
    setError(null);

    try {
      await api.acceptScriptRevision(episodeId);
      setPendingRevision(null);
      setIsVersionHistoryLoaded(false); // Force reload versions
      onScriptUpdated();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to accept revision: ${err.message}`);
      } else {
        setError("Failed to accept revision");
      }
    } finally {
      setIsAcceptingRevision(false);
    }
  };

  // Reject revision
  const handleRejectRevision = () => {
    setPendingRevision(null);
    setError(null);
  };

  // Restore version
  const handleRestoreVersion = async (version: number) => {
    setIsRestoringVersion(true);
    setRestoringVersion(version);
    setError(null);

    try {
      await api.restoreScriptVersion(episodeId, version);
      setIsVersionHistoryLoaded(false); // Force reload versions
      onScriptUpdated();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Failed to restore version: ${err.message}`);
      } else {
        setError("Failed to restore version");
      }
    } finally {
      setIsRestoringVersion(false);
      setRestoringVersion(null);
    }
  };

  // No script content
  if (!script || !script.full_text) {
    return (
      <Card>
        <CardContent>
          <div className="text-center py-8">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No Script Available</h3>
            <p className="mt-1 text-sm text-gray-500">
              Run the scripting stage to generate a script for this episode.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Error Alert */}
      {error && (
        <Alert variant="error" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Revision Review Mode */}
      {hasPendingRevision && pendingRevision && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">Review Proposed Revision</CardTitle>
              <Badge variant="warning">Pending Review</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Revision Instructions */}
            <div className="p-3 bg-gray-50 rounded-md border border-gray-200">
              <span className="text-xs text-gray-500 uppercase tracking-wide">Revision Instructions</span>
              <p className="mt-1 text-sm text-gray-700">{pendingRevision.revision_instructions}</p>
            </div>

            {/* Diff View */}
            <DiffView
              original={pendingRevision.original_script}
              revised={pendingRevision.proposed_revision}
            />

            {/* Model Info */}
            <div className="text-xs text-gray-500">
              Generated using <span className="font-mono">{pendingRevision.model_used}</span>
            </div>
          </CardContent>
          <CardFooter>
            <Button
              variant="ghost"
              onClick={handleRejectRevision}
              disabled={isAcceptingRevision}
            >
              Reject
            </Button>
            <Button
              variant="primary"
              onClick={handleAcceptRevision}
              loading={isAcceptingRevision}
            >
              Accept Revision
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* Main Script Display */}
      {!hasPendingRevision && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Script</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsRevisionModalOpen(true)}
              leftIcon={
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              }
            >
              Request Revision
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Script Stats */}
            <ScriptStats
              wordCount={script.word_count}
              estimatedDuration={script.estimated_duration_seconds}
              modelUsed={script.model_used}
              version={script.version}
            />

            {/* Script Text */}
            <div className="max-h-[500px] overflow-y-auto rounded-md border border-gray-200 bg-gray-50 p-4">
              <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                {script.full_text}
              </p>
            </div>

            {/* Generation Date */}
            {script.generated_at && (
              <div className="text-xs text-gray-500">
                Generated on {formatDate(script.generated_at)}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Version History */}
      <div onMouseEnter={loadVersionHistory}>
        {isLoadingVersions ? (
          <Card variant="outline" padding="sm">
            <div className="flex items-center justify-center py-4">
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Loading version history...
              </div>
            </div>
          </Card>
        ) : isVersionHistoryLoaded ? (
          <VersionHistory
            versions={versions}
            currentVersion={script.version}
            onRestore={handleRestoreVersion}
            isRestoring={isRestoringVersion}
            restoringVersion={restoringVersion}
          />
        ) : (
          <Card variant="outline" padding="none">
            <button
              onClick={loadVersionHistory}
              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm font-medium text-gray-700">Version History</span>
              </div>
              <span className="text-xs text-gray-500">Click to load</span>
            </button>
          </Card>
        )}
      </div>

      {/* Revision Modal */}
      <RevisionModal
        isOpen={isRevisionModalOpen}
        onClose={() => setIsRevisionModalOpen(false)}
        onSubmit={handleRequestRevision}
        isLoading={isRequestingRevision}
      />
    </div>
  );
}
