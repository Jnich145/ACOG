"use client";

import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { LoadingText } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { formatDuration, snakeToTitle } from "@/lib/utils";
import type {
  PipelineStatusResponse,
  PipelineStageInfo,
} from "@/lib/types";

// Pipeline stages in order - currently implemented stages
// Future stages (script_review, assembly, upload) are not yet implemented
const PIPELINE_STAGES = [
  "planning",
  "scripting",
  "metadata",
  "audio",
  "avatar",
  "broll",
];

interface PipelineStatusProps {
  status: PipelineStatusResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error?: Error | null;
}

export function PipelineStatus({
  status,
  isLoading,
  isError,
  error,
}: PipelineStatusProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent>
          <LoadingText text="Loading pipeline status..." />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="error" title="Failed to load pipeline status">
            {error?.message || "Could not fetch pipeline status."}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">No pipeline data available.</p>
        </CardContent>
      </Card>
    );
  }

  const { pipeline_progress, stages, active_jobs } = status;

  return (
    <Card padding="none">
      <CardHeader className="px-6 pt-6 pb-4">
        <CardTitle>Pipeline Status</CardTitle>
        <div className="text-sm text-gray-500">
          {pipeline_progress.completed_stages} of {pipeline_progress.total_stages} stages complete
          ({pipeline_progress.percent_complete}%)
        </div>
      </CardHeader>

      <CardContent className="px-6 pb-6">
        {/* Progress bar */}
        <div className="mb-6">
          <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-600 transition-all duration-500"
              style={{ width: `${pipeline_progress.percent_complete}%` }}
            />
          </div>
        </div>

        {/* Active jobs indicator */}
        {active_jobs && active_jobs.length > 0 && (
          <div className="mb-4 p-3 bg-blue-50 rounded-md border border-blue-100">
            <div className="flex items-center gap-2">
              <span className="status-dot status-dot-processing" />
              <span className="text-sm font-medium text-blue-700">
                Running: {active_jobs.map((j) => snakeToTitle(j.stage)).join(", ")}
              </span>
            </div>
          </div>
        )}

        {/* Stage list */}
        <div className="space-y-1">
          {PIPELINE_STAGES.map((stageName) => {
            const stageInfo = stages[stageName];
            return (
              <StageRow
                key={stageName}
                name={stageName}
                info={stageInfo}
              />
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

interface StageRowProps {
  name: string;
  info: PipelineStageInfo | undefined;
}

function StageRow({ name, info }: StageRowProps) {
  const status = info?.status || "pending";
  const hasError = status === "failed" && info?.error;

  return (
    <div
      className={cn(
        "flex items-center justify-between py-2 px-3 rounded-md",
        {
          "bg-green-50": status === "completed",
          "bg-blue-50": status === "processing" || status === "queued",
          "bg-red-50": status === "failed",
          "bg-gray-50": status === "pending" || status === "skipped",
        }
      )}
    >
      <div className="flex items-center gap-3">
        <StageStatusIcon status={status} />
        <span
          className={cn("text-sm font-medium", {
            "text-green-700": status === "completed",
            "text-blue-700": status === "processing" || status === "queued",
            "text-red-700": status === "failed",
            "text-gray-600": status === "pending" || status === "skipped",
          })}
        >
          {snakeToTitle(name)}
        </span>
      </div>

      <div className="flex items-center gap-4 text-xs">
        {info?.duration_seconds && (
          <span className="text-gray-500">
            {formatDuration(info.duration_seconds)}
          </span>
        )}
        {info?.attempts && info.attempts > 1 && (
          <span className="text-gray-500">
            {info.attempts} attempts
          </span>
        )}
        {hasError && (
          <span className="text-red-600 max-w-[200px] truncate" title={info.error || ""}>
            {info.error}
          </span>
        )}
      </div>
    </div>
  );
}

interface StageStatusIconProps {
  status: string;
}

function StageStatusIcon({ status }: StageStatusIconProps) {
  switch (status) {
    case "completed":
      return (
        <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
            clipRule="evenodd"
          />
        </svg>
      );
    case "processing":
      return (
        <svg
          className="w-5 h-5 text-blue-500 animate-spin"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      );
    case "queued":
      return (
        <svg className="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
            clipRule="evenodd"
          />
        </svg>
      );
    case "failed":
      return (
        <svg className="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clipRule="evenodd"
          />
        </svg>
      );
    default:
      return (
        <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z"
            clipRule="evenodd"
          />
        </svg>
      );
  }
}
