"use client";

import Link from "next/link";
import { LoadingScreen } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { StatusBadge } from "@/components/ui/Badge";
import { formatDateShort, truncate } from "@/lib/utils";
import { STATUS_CONFIG, PRIORITY_CONFIG } from "@/lib/types";
import type { Episode, EpisodeStatus, Priority } from "@/lib/types";

interface EpisodeListProps {
  episodes: Episode[] | undefined;
  isLoading: boolean;
  isError: boolean;
  error?: Error | null;
  showChannel?: boolean;
}

export function EpisodeList({
  episodes,
  isLoading,
  isError,
  error,
  showChannel = false,
}: EpisodeListProps) {
  if (isLoading) {
    return <LoadingScreen />;
  }

  if (isError) {
    return (
      <Alert variant="error" title="Failed to load episodes">
        {error?.message || "An error occurred while fetching episodes."}
      </Alert>
    );
  }

  if (!episodes || episodes.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
          />
        </svg>
        <h3 className="mt-4 text-lg font-medium text-gray-900">No episodes</h3>
        <p className="mt-2 text-sm text-gray-500">
          Get started by creating your first episode.
        </p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Priority</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {episodes.map((episode) => (
            <EpisodeRow key={episode.id} episode={episode} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface EpisodeRowProps {
  episode: Episode;
}

function EpisodeRow({ episode }: EpisodeRowProps) {
  const statusConfig = STATUS_CONFIG[episode.status as EpisodeStatus] || STATUS_CONFIG.idea;
  const priorityConfig = PRIORITY_CONFIG[episode.priority as Priority] || PRIORITY_CONFIG.normal;

  // Map status to badge variant
  const getStatusVariant = (status: EpisodeStatus) => {
    switch (status) {
      case "published":
      case "ready":
        return "success" as const;
      case "planning":
      case "scripting":
      case "audio":
      case "avatar":
      case "broll":
      case "assembly":
      case "publishing":
        return "info" as const;
      case "script_review":
        return "warning" as const;
      case "failed":
        return "error" as const;
      default:
        return "default" as const;
    }
  };

  // Map priority to badge variant
  const getPriorityVariant = (priority: Priority) => {
    switch (priority) {
      case "urgent":
        return "error" as const;
      case "high":
        return "warning" as const;
      case "normal":
        return "info" as const;
      default:
        return "default" as const;
    }
  };

  return (
    <tr>
      <td>
        <Link
          href={`/episodes/${episode.id}`}
          className="font-medium text-primary-600 hover:text-primary-700"
        >
          {episode.title || "Untitled Episode"}
        </Link>
        {episode.idea_brief && (
          <p className="text-xs text-gray-500 mt-0.5">
            {truncate(episode.idea_brief, 60)}
          </p>
        )}
      </td>
      <td>
        <StatusBadge variant={getStatusVariant(episode.status)}>
          {statusConfig.label}
        </StatusBadge>
      </td>
      <td>
        <StatusBadge variant={getPriorityVariant(episode.priority)} showDot={false}>
          {priorityConfig.label}
        </StatusBadge>
      </td>
      <td className="text-gray-500">{formatDateShort(episode.created_at)}</td>
    </tr>
  );
}
