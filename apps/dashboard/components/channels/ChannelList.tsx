"use client";

import Link from "next/link";
import { useChannels } from "@/hooks/useChannels";
import { LoadingScreen } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { formatDateShort } from "@/lib/utils";
import type { Channel } from "@/lib/types";

export function ChannelList() {
  const { channels, isLoading, isError, error } = useChannels();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (isError) {
    return (
      <Alert variant="error" title="Failed to load channels">
        {error?.message || "An error occurred while fetching channels."}
      </Alert>
    );
  }

  if (!channels || channels.length === 0) {
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
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          />
        </svg>
        <h3 className="mt-4 text-lg font-medium text-gray-900">No channels</h3>
        <p className="mt-2 text-sm text-gray-500">
          Get started by creating your first channel.
        </p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Niche</th>
            <th>Episodes</th>
            <th>Status</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((channel) => (
            <ChannelRow key={channel.id} channel={channel} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface ChannelRowProps {
  channel: Channel;
}

function ChannelRow({ channel }: ChannelRowProps) {
  return (
    <tr>
      <td>
        <Link
          href={`/channels/${channel.id}`}
          className="font-medium text-primary-600 hover:text-primary-700"
        >
          {channel.name}
        </Link>
        <p className="text-xs text-gray-500 mt-0.5">{channel.slug}</p>
      </td>
      <td>
        {channel.niche ? (
          <span className="text-gray-700">{channel.niche}</span>
        ) : (
          <span className="text-gray-400">-</span>
        )}
      </td>
      <td>
        <span className="font-medium">{channel.episode_count}</span>
      </td>
      <td>
        <Badge variant={channel.is_active ? "success" : "default"}>
          {channel.is_active ? "Active" : "Inactive"}
        </Badge>
      </td>
      <td className="text-gray-500">{formatDateShort(channel.created_at)}</td>
    </tr>
  );
}
