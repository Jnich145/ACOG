"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { formatDate, snakeToTitle } from "@/lib/utils";
import { api, isApiError } from "@/lib/api";
import type { Job } from "@/lib/types";
import { PIPELINE_STAGES } from "@/lib/types";

interface EpisodeFailurePanelProps {
  jobs: Job[] | undefined;
  isLoading: boolean;
  isError: boolean;
  episodeId: string;
  onRetryStarted?: () => void;
}

// Valid pipeline stages that can be retried
// Excludes orchestrator pseudo-stages like "stage_1_pipeline" and "full_pipeline"
const RETRYABLE_STAGES = new Set<string>(PIPELINE_STAGES);

/**
 * Displays failure information for the most recent failed job.
 * Only renders when there is at least one failed job with a valid pipeline stage.
 * Excludes orchestrator pseudo-stages (stage_1_pipeline, full_pipeline) since they
 * cannot be directly retried through the trigger endpoint.
 */
export function EpisodeFailurePanel({
  jobs,
  isLoading,
  isError,
  episodeId,
  onRetryStarted,
}: EpisodeFailurePanelProps) {
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  // Don't show anything while loading or on error fetching jobs
  if (isLoading || isError || !jobs) {
    return null;
  }

  // Find the most recent failed job with a valid pipeline stage
  // Jobs are sorted by created_at desc from API
  // Exclude orchestrator pseudo-stages that can't be retried directly
  const failedJob = jobs.find(
    (job) => job.status === "failed" && RETRYABLE_STAGES.has(job.stage)
  );

  // No failed jobs - don't render anything
  if (!failedJob) {
    return null;
  }

  // Format the timestamp - prefer completed_at, fall back to updated_at or created_at
  const failedAt =
    failedJob.completed_at || failedJob.updated_at || failedJob.created_at;

  const handleRetry = async () => {
    setIsRetrying(true);
    setRetryError(null);

    try {
      await api.retryStage(episodeId, failedJob.stage);
      // Notify parent to start polling
      onRetryStarted?.();
    } catch (err) {
      if (isApiError(err)) {
        setRetryError(err.message);
      } else {
        setRetryError("Failed to retry stage. Please try again.");
      }
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <Alert variant="error" title="Pipeline Failure" className="mb-6">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="font-medium">Stage:</span>
          <span>{snakeToTitle(failedJob.stage)}</span>
        </div>
        {failedJob.error_message && (
          <div>
            <span className="font-medium">Error:</span>{" "}
            <span className="break-words">{failedJob.error_message}</span>
          </div>
        )}
        {failedAt && (
          <div className="text-xs text-red-600">
            Failed at: {formatDate(failedAt)}
          </div>
        )}
        {retryError && (
          <div className="text-xs text-red-800 bg-red-100 p-2 rounded">
            Retry failed: {retryError}
          </div>
        )}
        <div className="pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
            loading={isRetrying}
            disabled={isRetrying}
          >
            Retry from {snakeToTitle(failedJob.stage)}
          </Button>
        </div>
      </div>
    </Alert>
  );
}
