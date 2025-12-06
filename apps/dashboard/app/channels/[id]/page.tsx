"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LoadingScreen } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { EpisodeList, CreateEpisodeForm } from "@/components/episodes";
import { useChannel, useChannelEpisodes } from "@/hooks/useChannel";
import { formatDateShort } from "@/lib/utils";
import type { Persona } from "@/lib/types";

export default function ChannelDetailPage() {
  const params = useParams();
  const channelId = params.id as string;

  const { channel, isLoading: isLoadingChannel, isError: isChannelError, error: channelError } = useChannel(channelId);
  const { episodes, isLoading: isLoadingEpisodes, isError: isEpisodesError, error: episodesError, mutate: mutateEpisodes } = useChannelEpisodes(channelId);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  if (isLoadingChannel) {
    return <LoadingScreen />;
  }

  if (isChannelError || !channel) {
    return (
      <Alert variant="error" title="Failed to load channel">
        {channelError?.message || "Could not fetch channel details."}
      </Alert>
    );
  }

  // Parse persona from channel data (safely handle unknown structure)
  const persona = channel.persona as Partial<Persona> | undefined;

  return (
    <>
      <Header
        title={channel.name}
        subtitle={channel.description || undefined}
        breadcrumbs={[
          { label: "Channels", href: "/channels" },
          { label: channel.name },
        ]}
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

      {/* Channel Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {/* Overview Card */}
        <Card>
          <CardContent>
            <h3 className="text-sm font-medium text-gray-500 mb-3">Overview</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Slug</dt>
                <dd className="font-mono text-gray-900">{channel.slug}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Niche</dt>
                <dd className="text-gray-900">{channel.niche || "-"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Status</dt>
                <dd>
                  <Badge variant={channel.is_active ? "success" : "default"}>
                    {channel.is_active ? "Active" : "Inactive"}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-900">{formatDateShort(channel.created_at)}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Persona Card */}
        <Card>
          <CardContent>
            <h3 className="text-sm font-medium text-gray-500 mb-3">Persona</h3>
            {persona && persona.name ? (
              <div className="space-y-2">
                <p className="font-medium text-gray-900">{persona.name}</p>
                {persona.background && (
                  <p className="text-sm text-gray-600 line-clamp-4">
                    {persona.background}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No persona configured</p>
            )}
          </CardContent>
        </Card>

        {/* Stats Card */}
        <Card>
          <CardContent>
            <h3 className="text-sm font-medium text-gray-500 mb-3">Statistics</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Total Episodes</dt>
                <dd className="font-semibold text-gray-900">{channel.episode_count}</dd>
              </div>
              {channel.stats && (
                <>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Published</dt>
                    <dd className="font-semibold text-green-600">
                      {channel.stats.published_episodes}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">In Progress</dt>
                    <dd className="font-semibold text-blue-600">
                      {channel.stats.in_progress_episodes}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Failed</dt>
                    <dd className="font-semibold text-red-600">
                      {channel.stats.failed_episodes}
                    </dd>
                  </div>
                </>
              )}
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Episodes Section */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Episodes</h2>
        <EpisodeList
          episodes={episodes}
          isLoading={isLoadingEpisodes}
          isError={isEpisodesError}
          error={episodesError}
        />
      </div>

      {/* Create Episode Modal */}
      <CreateEpisodeForm
        channelId={channelId}
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSuccess={() => mutateEpisodes()}
      />
    </>
  );
}
