"use client";

import { Modal } from "@/components/ui/Modal";
import { Badge } from "@/components/ui/Badge";
import { formatJson, formatDateShort, snakeToTitle } from "@/lib/utils";
import type { Asset } from "@/lib/types";

interface AssetViewerProps {
  asset: Asset | null;
  isOpen: boolean;
  onClose: () => void;
}

export function AssetViewer({ asset, isOpen, onClose }: AssetViewerProps) {
  if (!asset) return null;

  // Get displayable content from the asset
  const content = getAssetContent(asset);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${snakeToTitle(asset.type)} Asset`}
      size="full"
    >
      <div className="space-y-4">
        {/* Asset metadata */}
        <div className="flex flex-wrap gap-4 text-sm">
          <div>
            <span className="text-gray-500">Type: </span>
            <Badge variant="info">{snakeToTitle(asset.type)}</Badge>
          </div>
          {asset.filename && (
            <div>
              <span className="text-gray-500">Filename: </span>
              <span className="font-mono">{asset.filename}</span>
            </div>
          )}
          <div>
            <span className="text-gray-500">Created: </span>
            <span>{formatDateShort(asset.created_at)}</span>
          </div>
          {asset.is_primary && (
            <Badge variant="success">Primary</Badge>
          )}
        </div>

        {/* Content display */}
        <div className="mt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Content</h4>
          <div className="code-block max-h-[60vh] overflow-y-auto">
            <pre className="text-sm whitespace-pre-wrap">{content}</pre>
          </div>
        </div>
      </div>
    </Modal>
  );
}

function getAssetContent(asset: Asset): string {
  // For plan, script, metadata - the content is in the metadata field
  const metadata = asset.metadata as Record<string, unknown>;

  if (metadata && Object.keys(metadata).length > 0) {
    // Check for common content keys
    if (metadata.content) {
      if (typeof metadata.content === "string") {
        return metadata.content;
      }
      return formatJson(metadata.content);
    }

    // Check for plan data
    if (metadata.plan) {
      return formatJson(metadata.plan);
    }

    // Check for script data
    if (metadata.script || metadata.full_text) {
      const scriptData = (metadata.script || metadata) as Record<string, unknown>;
      if (typeof scriptData.full_text === "string") {
        return scriptData.full_text;
      }
      return formatJson(scriptData);
    }

    // Return the whole metadata as JSON
    return formatJson(metadata);
  }

  return "No content available for this asset.";
}
