"use client";

import { LoadingText } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDateShort, formatFileSize, snakeToTitle } from "@/lib/utils";
import type { Asset, AssetType } from "@/lib/types";

interface AssetListProps {
  assets: Asset[] | undefined;
  isLoading: boolean;
  isError: boolean;
  error?: Error | null;
  onViewAsset?: (asset: Asset) => void;
}

// Map asset types to badge variants
const getAssetTypeVariant = (type: AssetType) => {
  switch (type) {
    case "plan":
    case "script":
    case "metadata":
      return "info" as const;
    case "audio":
      return "secondary" as const;
    case "avatar_video":
    case "b_roll":
    case "assembled_video":
      return "success" as const;
    case "thumbnail":
      return "warning" as const;
    default:
      return "default" as const;
  }
};

export function AssetList({
  assets,
  isLoading,
  isError,
  error,
  onViewAsset,
}: AssetListProps) {
  if (isLoading) {
    return <LoadingText text="Loading assets..." />;
  }

  if (isError) {
    return (
      <Alert variant="error" title="Failed to load assets">
        {error?.message || "Could not fetch assets."}
      </Alert>
    );
  }

  if (!assets || assets.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <svg
          className="mx-auto h-10 w-10 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"
          />
        </svg>
        <p className="mt-2 text-sm">No assets generated yet</p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Filename</th>
            <th>Size</th>
            <th>Created</th>
            <th className="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.id}>
              <td>
                <Badge variant={getAssetTypeVariant(asset.type)}>
                  {snakeToTitle(asset.type)}
                </Badge>
              </td>
              <td>
                <span className="font-mono text-sm text-gray-700">
                  {asset.filename || "-"}
                </span>
              </td>
              <td className="text-gray-500">
                {formatFileSize(asset.size_bytes)}
              </td>
              <td className="text-gray-500">
                {formatDateShort(asset.created_at)}
              </td>
              <td className="text-right">
                {canViewAsset(asset.type) && onViewAsset && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onViewAsset(asset)}
                  >
                    View
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Determine if an asset type can be viewed in the modal
function canViewAsset(type: AssetType): boolean {
  return ["plan", "script", "metadata"].includes(type);
}
