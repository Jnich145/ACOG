"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { LoadingScreen } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { PipelineStatus, PlanViewer, MetadataViewer, EpisodeFailurePanel } from "@/components/episodes";
import { AssetList, AssetViewer } from "@/components/assets";
import { useEpisode } from "@/hooks/useEpisode";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";
import { useAssets } from "@/hooks/useAssets";
import { useJobs } from "@/hooks/useJobs";
import { api, isApiError } from "@/lib/api";
import { formatDate, cn } from "@/lib/utils";
import {
  STATUS_CONFIG,
  PRIORITY_CONFIG,
  type Asset,
  type EpisodeStatus,
  type Priority,
} from "@/lib/types";

type TabId = "overview" | "plan" | "script" | "metadata" | "assets";

interface Tab {
  id: TabId;
  label: string;
  badge?: number | string;
}

export default function EpisodeDetailPage() {
  const params = useParams();
  const episodeId = params.id as string;

  const { episode, isLoading: isLoadingEpisode, isError: isEpisodeError, error: episodeError, mutate: mutateEpisode } = useEpisode(episodeId);

  // Determine if we should poll for pipeline status
  const [shouldPoll, setShouldPoll] = useState(false);

  const {
    status: pipelineStatus,
    isLoading: isLoadingPipeline,
    isError: isPipelineError,
    error: pipelineError,
    isRunning,
    mutate: mutatePipeline,
  } = usePipelineStatus(episodeId, shouldPoll);

  const {
    assets,
    isLoading: isLoadingAssets,
    isError: isAssetsError,
    error: assetsError,
    mutate: mutateAssets,
  } = useAssets(episodeId);

  const {
    jobs,
    isLoading: isLoadingJobs,
    isError: isJobsError,
  } = useJobs(episodeId);

  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  // Asset viewer state
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [isViewerOpen, setIsViewerOpen] = useState(false);

  // Pipeline trigger state
  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  // Update polling state based on active jobs
  useEffect(() => {
    setShouldPoll(isRunning || false);
  }, [isRunning]);

  // Handlers
  const handleViewAsset = (asset: Asset) => {
    setSelectedAsset(asset);
    setIsViewerOpen(true);
  };

  const handleCloseViewer = () => {
    setIsViewerOpen(false);
    setSelectedAsset(null);
  };

  const handleRunStage1 = async () => {
    setIsTriggering(true);
    setTriggerError(null);

    try {
      await api.runStage1(episodeId);

      // Start polling for status updates
      setShouldPoll(true);

      // Refresh data
      await Promise.all([mutateEpisode(), mutatePipeline(), mutateAssets()]);
    } catch (err) {
      if (isApiError(err)) {
        setTriggerError(err.message);
      } else {
        setTriggerError("Failed to trigger pipeline. Please try again.");
      }
    } finally {
      setIsTriggering(false);
    }
  };

  const handleRunFullPipeline = async () => {
    setIsTriggering(true);
    setTriggerError(null);

    try {
      await api.runFullPipeline(episodeId);

      // Start polling for status updates
      setShouldPoll(true);

      // Refresh data
      await Promise.all([mutateEpisode(), mutatePipeline(), mutateAssets()]);
    } catch (err) {
      if (isApiError(err)) {
        setTriggerError(err.message);
      } else {
        setTriggerError("Failed to trigger full pipeline. Please try again.");
      }
    } finally {
      setIsTriggering(false);
    }
  };

  // Loading state
  if (isLoadingEpisode) {
    return <LoadingScreen />;
  }

  // Error state
  if (isEpisodeError || !episode) {
    return (
      <Alert variant="error" title="Failed to load episode">
        {episodeError?.message || "Could not fetch episode details."}
      </Alert>
    );
  }

  // Get status configuration
  const statusConfig = STATUS_CONFIG[episode.status as EpisodeStatus] || STATUS_CONFIG.idea;
  const priorityConfig = PRIORITY_CONFIG[episode.priority as Priority] || PRIORITY_CONFIG.normal;

  // Determine if Stage 1 can be run
  const canRunStage1 = ["idea", "failed", "cancelled"].includes(episode.status);

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

  // Build tabs based on available data
  const tabs: Tab[] = [
    { id: "overview", label: "Overview" },
  ];

  if (episode.plan && Object.keys(episode.plan).length > 0) {
    tabs.push({ id: "plan", label: "Plan" });
  }

  if (episode.script?.full_text) {
    tabs.push({ id: "script", label: "Script" });
  }

  if (episode.metadata && Object.keys(episode.metadata).length > 0) {
    tabs.push({ id: "metadata", label: "Metadata" });
  }

  tabs.push({ id: "assets", label: "Assets", badge: assets?.length || 0 });

  return (
    <>
      <Header
        title={episode.title || "Untitled Episode"}
        breadcrumbs={[
          { label: "Channels", href: "/channels" },
          { label: "Channel", href: `/channels/${episode.channel_id}` },
          { label: episode.title || "Episode" },
        ]}
        actions={
          <div className="flex items-center gap-3">
            <StatusBadge variant={getStatusVariant(episode.status)}>
              {statusConfig.label}
            </StatusBadge>
            {canRunStage1 && !isRunning && (
              <>
                <Button
                  variant="outline"
                  onClick={handleRunStage1}
                  loading={isTriggering}
                  disabled={isRunning}
                >
                  Run Stage 1
                </Button>
                <Button
                  onClick={handleRunFullPipeline}
                  loading={isTriggering}
                  disabled={isRunning}
                >
                  Run Full Pipeline
                </Button>
              </>
            )}
            {isRunning && (
              <Button disabled loading>
                Pipeline Running...
              </Button>
            )}
          </div>
        }
      />

      {/* Pipeline Failure Panel */}
      <EpisodeFailurePanel
        jobs={jobs}
        isLoading={isLoadingJobs}
        isError={isJobsError}
      />

      {/* Trigger Error Alert */}
      {triggerError && (
        <Alert
          variant="error"
          title="Failed to run pipeline"
          className="mb-6"
          onDismiss={() => setTriggerError(null)}
        >
          {triggerError}
        </Alert>
      )}

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "py-3 px-1 border-b-2 font-medium text-sm whitespace-nowrap",
                activeTab === tab.id
                  ? "border-primary-500 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              )}
            >
              {tab.label}
              {tab.badge !== undefined && (
                <span className={cn(
                  "ml-2 py-0.5 px-2 rounded-full text-xs",
                  activeTab === tab.id
                    ? "bg-primary-100 text-primary-600"
                    : "bg-gray-100 text-gray-600"
                )}>
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {/* Overview Tab */}
        {activeTab === "overview" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column - Episode details */}
            <div className="lg:col-span-1 space-y-6">
              {/* Episode Info Card */}
              <Card>
                <CardHeader>
                  <CardTitle>Episode Details</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="space-y-3 text-sm">
                    <div>
                      <dt className="text-gray-500">Status</dt>
                      <dd className="mt-1">
                        <StatusBadge variant={getStatusVariant(episode.status)}>
                          {statusConfig.label}
                        </StatusBadge>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Priority</dt>
                      <dd className="mt-1">
                        <Badge variant={episode.priority === "urgent" ? "error" : episode.priority === "high" ? "warning" : "default"}>
                          {priorityConfig.label}
                        </Badge>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Idea Source</dt>
                      <dd className="mt-1 text-gray-900 capitalize">{episode.idea_source}</dd>
                    </div>
                    {episode.target_length_minutes && (
                      <div>
                        <dt className="text-gray-500">Target Length</dt>
                        <dd className="mt-1 text-gray-900">{episode.target_length_minutes} minutes</dd>
                      </div>
                    )}
                    {episode.tags && episode.tags.length > 0 && (
                      <div>
                        <dt className="text-gray-500">Tags</dt>
                        <dd className="mt-1 flex flex-wrap gap-1">
                          {episode.tags.map((tag, index) => (
                            <span key={index} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">
                              {tag}
                            </span>
                          ))}
                        </dd>
                      </div>
                    )}
                    <div>
                      <dt className="text-gray-500">Assets</dt>
                      <dd className="mt-1 text-gray-900">{assets?.length ?? episode.asset_count}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Created</dt>
                      <dd className="mt-1 text-gray-900">{formatDate(episode.created_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Updated</dt>
                      <dd className="mt-1 text-gray-900">{formatDate(episode.updated_at)}</dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>

              {/* Idea Brief Card */}
              {episode.idea_brief && (
                <Card>
                  <CardHeader>
                    <CardTitle>Idea Brief</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">
                      {episode.idea_brief}
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Right column - Pipeline Status */}
            <div className="lg:col-span-2 space-y-6">
              {/* Pipeline Status */}
              <PipelineStatus
                status={pipelineStatus}
                isLoading={isLoadingPipeline}
                isError={isPipelineError}
                error={pipelineError}
              />

              {/* Quick Stats */}
              {(episode.plan || episode.metadata) && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {episode.plan && (
                    <>
                      <Card>
                        <CardContent className="py-4">
                          <div className="text-2xl font-bold text-primary-600">
                            {(episode.plan as Record<string, unknown[]>).sections?.length || 0}
                          </div>
                          <div className="text-xs text-gray-500">Sections</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="py-4">
                          <div className="text-2xl font-bold text-primary-600">
                            {(episode.plan as Record<string, unknown[]>).hooks?.length || 0}
                          </div>
                          <div className="text-xs text-gray-500">Hooks</div>
                        </CardContent>
                      </Card>
                    </>
                  )}
                  {episode.metadata && (
                    <>
                      <Card>
                        <CardContent className="py-4">
                          <div className="text-2xl font-bold text-primary-600">
                            {(episode.metadata as Record<string, unknown[]>).title_options?.length || 0}
                          </div>
                          <div className="text-xs text-gray-500">Title Options</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="py-4">
                          <div className="text-2xl font-bold text-primary-600">
                            {(episode.metadata as Record<string, unknown[]>).chapters?.length || 0}
                          </div>
                          <div className="text-xs text-gray-500">Chapters</div>
                        </CardContent>
                      </Card>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Plan Tab */}
        {activeTab === "plan" && episode.plan && (
          <div className="max-w-4xl">
            <PlanViewer plan={episode.plan} />
          </div>
        )}

        {/* Script Tab */}
        {activeTab === "script" && episode.script?.full_text && (
          <div className="max-w-4xl">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Full Script</CardTitle>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
                    <span>{episode.script.word_count} words</span>
                    <span>~{Math.round(episode.script.estimated_duration_seconds / 60)} min</span>
                    {episode.script.model_used && (
                      <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">
                        {episode.script.model_used}
                      </span>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="bg-gray-50 rounded-md p-6 max-h-[600px] overflow-y-auto">
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                    {episode.script.full_text}
                  </pre>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Metadata Tab */}
        {activeTab === "metadata" && episode.metadata && (
          <div className="max-w-4xl">
            <MetadataViewer metadata={episode.metadata} />
          </div>
        )}

        {/* Assets Tab */}
        {activeTab === "assets" && (
          <Card padding="none">
            <CardHeader className="px-6 pt-6 pb-4">
              <CardTitle>Assets</CardTitle>
              <span className="text-sm text-gray-500">
                {assets?.length || 0} assets
              </span>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <AssetList
                assets={assets}
                isLoading={isLoadingAssets}
                isError={isAssetsError}
                error={assetsError}
                onViewAsset={handleViewAsset}
              />
            </CardContent>
          </Card>
        )}
      </div>

      {/* Asset Viewer Modal */}
      <AssetViewer
        asset={selectedAsset}
        isOpen={isViewerOpen}
        onClose={handleCloseViewer}
      />
    </>
  );
}
