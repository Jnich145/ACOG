"use client";

import { Alert } from "@/components/ui/Alert";
import { formatDate, snakeToTitle } from "@/lib/utils";
import type { Job } from "@/lib/types";

interface EpisodeFailurePanelProps {
  jobs: Job[] | undefined;
  isLoading: boolean;
  isError: boolean;
}

/**
 * Displays failure information for the most recent failed job.
 * Only renders when there is at least one failed job.
 */
export function EpisodeFailurePanel({
  jobs,
  isLoading,
  isError,
}: EpisodeFailurePanelProps) {
  // Don't show anything while loading or on error fetching jobs
  if (isLoading || isError || !jobs) {
    return null;
  }

  // Find the most recent failed job (jobs are sorted by created_at desc from API)
  const failedJob = jobs.find((job) => job.status === "failed");

  // No failed jobs - don't render anything
  if (!failedJob) {
    return null;
  }

  // Format the timestamp - prefer completed_at, fall back to updated_at or created_at
  const failedAt =
    failedJob.completed_at || failedJob.updated_at || failedJob.created_at;

  return (
    <Alert variant="error" title="Pipeline Failure" className="mb-6">
      <div className="space-y-1">
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
          <div className="text-xs text-red-600 mt-2">
            Failed at: {formatDate(failedAt)}
          </div>
        )}
      </div>
    </Alert>
  );
}
