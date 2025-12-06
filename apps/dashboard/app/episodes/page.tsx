"use client";

import { useState } from "react";
import useSWR from "swr";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { LoadingScreen, LoadingText } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Modal, ModalFooter } from "@/components/ui/Modal";
import { Input, Textarea, Select, type SelectOption } from "@/components/ui/Input";
import { swrFetcher, api, isApiError } from "@/lib/api";
import { formatDateShort, cn } from "@/lib/utils";
import {
  STATUS_CONFIG,
  PRIORITY_CONFIG,
  type Episode,
  type EpisodeStatus,
  type Priority,
  type Channel,
} from "@/lib/types";
import Link from "next/link";
import { useRouter } from "next/navigation";

// Status filter options
const STATUS_FILTER_OPTIONS: SelectOption[] = [
  { value: "all", label: "All Statuses" },
  { value: "idea", label: "Idea" },
  { value: "planning", label: "Planning" },
  { value: "scripting", label: "Scripting" },
  { value: "script_review", label: "Script Review" },
  { value: "ready", label: "Ready" },
  { value: "failed", label: "Failed" },
];

// Priority options for create form
const PRIORITY_OPTIONS: SelectOption[] = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

export default function EpisodesPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState("all");

  // Fetch all episodes
  const {
    data: episodes,
    error: episodesError,
    isLoading: isLoadingEpisodes,
    mutate: mutateEpisodes,
  } = useSWR<Episode[]>("/episodes", swrFetcher);

  // Fetch all channels (for the create form)
  const {
    data: channels,
    error: channelsError,
    isLoading: isLoadingChannels,
  } = useSWR<Channel[]>("/channels", swrFetcher);

  // Create modal state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    channelId: "",
    title: "",
    ideaBrief: "",
    priority: "normal" as Priority,
  });

  // Filter episodes by status
  const filteredEpisodes = episodes?.filter((episode) =>
    statusFilter === "all" ? true : episode.status === statusFilter
  );

  // Get status variant for badge
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

  // Handle form changes
  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setCreateError(null);
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.channelId) {
      setCreateError("Please select a channel");
      return;
    }

    if (!formData.title.trim()) {
      setCreateError("Episode title is required");
      return;
    }

    setIsSubmitting(true);
    setCreateError(null);

    try {
      const response = await api.createEpisode(formData.channelId, {
        title: formData.title.trim(),
        idea_brief: formData.ideaBrief.trim() || undefined,
        priority: formData.priority,
      });

      // Close modal and reset form
      setIsCreateModalOpen(false);
      setFormData({
        channelId: "",
        title: "",
        ideaBrief: "",
        priority: "normal",
      });

      // Refresh episodes list
      mutateEpisodes();

      // Navigate to the new episode
      router.push(`/episodes/${response.data.id}`);
    } catch (err) {
      if (isApiError(err)) {
        setCreateError(err.message);
      } else {
        setCreateError("Failed to create episode. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle modal close
  const handleCloseModal = () => {
    if (!isSubmitting) {
      setIsCreateModalOpen(false);
      setFormData({
        channelId: "",
        title: "",
        ideaBrief: "",
        priority: "normal",
      });
      setCreateError(null);
    }
  };

  // Build channel options for select
  const channelOptions: SelectOption[] = [
    { value: "", label: "Select a channel..." },
    ...(channels?.map((ch) => ({
      value: ch.id,
      label: ch.name,
    })) || []),
  ];

  if (isLoadingEpisodes) {
    return <LoadingScreen />;
  }

  if (episodesError) {
    return (
      <Alert variant="error" title="Failed to load episodes">
        {episodesError.message || "Could not fetch episodes."}
      </Alert>
    );
  }

  // Count by status for quick stats
  const statusCounts = episodes?.reduce(
    (acc, ep) => {
      acc[ep.status] = (acc[ep.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  ) || {};

  return (
    <>
      <Header
        title="Episodes"
        subtitle={`${episodes?.length || 0} total episodes across all channels`}
        actions={
          <Button onClick={() => setIsCreateModalOpen(true)}>
            <svg
              className="h-4 w-4 mr-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 4v16m8-8H4"
              />
            </svg>
            New Episode
          </Button>
        }
      />

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
        {[
          { key: "idea", label: "Ideas", color: "text-gray-600" },
          { key: "planning", label: "Planning", color: "text-blue-600" },
          { key: "scripting", label: "Scripting", color: "text-blue-600" },
          { key: "script_review", label: "Review", color: "text-yellow-600" },
          { key: "ready", label: "Ready", color: "text-green-600" },
          { key: "failed", label: "Failed", color: "text-red-600" },
        ].map((stat) => (
          <Card key={stat.key}>
            <CardContent className="py-4">
              <div className={cn("text-2xl font-bold", stat.color)}>
                {statusCounts[stat.key] || 0}
              </div>
              <div className="text-xs text-gray-500">{stat.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-48">
          <Select
            options={STATUS_FILTER_OPTIONS}
            value={statusFilter}
            onChange={(value) => setStatusFilter(value)}
          />
        </div>
        <span className="text-sm text-gray-500">
          Showing {filteredEpisodes?.length || 0} episodes
        </span>
      </div>

      {/* Episodes List */}
      {!filteredEpisodes || filteredEpisodes.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <h3 className="mt-4 text-sm font-medium text-gray-900">No episodes found</h3>
            <p className="mt-1 text-sm text-gray-500">
              {statusFilter === "all"
                ? "Get started by creating a new episode."
                : `No episodes with status "${statusFilter}".`}
            </p>
            {statusFilter === "all" && (
              <Button
                className="mt-4"
                onClick={() => setIsCreateModalOpen(true)}
              >
                Create Episode
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Episode
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Channel
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Assets
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredEpisodes.map((episode) => {
                const statusConfig = STATUS_CONFIG[episode.status] || STATUS_CONFIG.idea;
                const priorityConfig = PRIORITY_CONFIG[episode.priority] || PRIORITY_CONFIG.normal;
                const channel = channels?.find((ch) => ch.id === episode.channel_id);

                return (
                  <tr
                    key={episode.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => router.push(`/episodes/${episode.id}`)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-gray-900">
                          {episode.title || "Untitled Episode"}
                        </span>
                        {episode.idea_brief && (
                          <span className="text-xs text-gray-500 line-clamp-1 max-w-md">
                            {episode.idea_brief}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Link
                        href={`/channels/${episode.channel_id}`}
                        className="text-sm text-primary-600 hover:text-primary-700"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {channel?.name || "Unknown"}
                      </Link>
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge variant={getStatusVariant(episode.status)}>
                        {statusConfig.label}
                      </StatusBadge>
                    </td>
                    <td className="px-6 py-4">
                      <Badge
                        variant={
                          episode.priority === "urgent"
                            ? "error"
                            : episode.priority === "high"
                            ? "warning"
                            : "default"
                        }
                      >
                        {priorityConfig.label}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {episode.asset_count}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {formatDateShort(episode.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Episode Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={handleCloseModal}
        title="Create New Episode"
        description="Create a new episode that will go through the content pipeline."
        size="md"
      >
        <form onSubmit={handleSubmit}>
          {createError && (
            <Alert variant="error" className="mb-4" onDismiss={() => setCreateError(null)}>
              {createError}
            </Alert>
          )}

          {isLoadingChannels ? (
            <LoadingText text="Loading channels..." />
          ) : channelsError ? (
            <Alert variant="error" className="mb-4">
              Failed to load channels. Please try again.
            </Alert>
          ) : channels?.length === 0 ? (
            <Alert variant="warning" className="mb-4">
              No channels available. Please create a channel first.
            </Alert>
          ) : (
            <div className="space-y-4">
              <Select
                label="Channel"
                name="channelId"
                options={channelOptions}
                value={formData.channelId}
                onChange={(value) => handleChange("channelId", value)}
                required
                disabled={isSubmitting}
              />

              <Input
                label="Episode Title"
                name="title"
                placeholder="e.g., How AI is Transforming Healthcare"
                value={formData.title}
                onChange={(e) => handleChange("title", e.target.value)}
                required
                disabled={isSubmitting}
              />

              <Textarea
                label="Idea Brief"
                name="ideaBrief"
                placeholder="Describe the main topic, key points to cover, and any specific angles or perspectives..."
                value={formData.ideaBrief}
                onChange={(e) => handleChange("ideaBrief", e.target.value)}
                rows={4}
                hint="This will guide the AI planning and script generation"
                disabled={isSubmitting}
              />

              <Select
                label="Priority"
                name="priority"
                options={PRIORITY_OPTIONS}
                value={formData.priority}
                onChange={(value) => handleChange("priority", value)}
                hint="Higher priority episodes are processed first"
                disabled={isSubmitting}
              />
            </div>
          )}

          <ModalFooter className="-mx-6 -mb-4 mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={handleCloseModal}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={isSubmitting}
              disabled={!channels || channels.length === 0}
            >
              Create Episode
            </Button>
          </ModalFooter>
        </form>
      </Modal>
    </>
  );
}
