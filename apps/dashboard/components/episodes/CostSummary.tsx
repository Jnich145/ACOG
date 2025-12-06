"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { LoadingText } from "@/components/ui/Spinner";
import { snakeToTitle } from "@/lib/utils";
import type { Job } from "@/lib/types";

interface CostSummaryProps {
  jobs: Job[] | undefined;
  isLoading: boolean;
  isError: boolean;
}

interface StageCost {
  stage: string;
  cost: number;
  tokens: number;
  jobCount: number;
}

/**
 * Displays estimated internal cost summary based on ACOG job data.
 * Sums cost_usd and tokens_used from completed jobs by stage.
 */
export function CostSummary({ jobs, isLoading, isError }: CostSummaryProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Estimated Cost</CardTitle>
        </CardHeader>
        <CardContent>
          <LoadingText text="Loading cost data..." />
        </CardContent>
      </Card>
    );
  }

  if (isError || !jobs) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Estimated Cost</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">Unable to load cost data.</p>
        </CardContent>
      </Card>
    );
  }

  // Only count completed jobs for cost
  const completedJobs = jobs.filter((job) => job.status === "completed");

  if (completedJobs.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Estimated Cost</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">
            No completed jobs yet. Cost data will appear after pipeline stages complete.
          </p>
        </CardContent>
      </Card>
    );
  }

  // Aggregate costs by stage
  const costsByStage = completedJobs.reduce<Record<string, StageCost>>((acc, job) => {
    const stage = job.stage;
    if (!acc[stage]) {
      acc[stage] = { stage, cost: 0, tokens: 0, jobCount: 0 };
    }
    acc[stage].cost += job.cost_usd ?? 0;
    acc[stage].tokens += job.tokens_used ?? 0;
    acc[stage].jobCount += 1;
    return acc;
  }, {});

  const stageEntries = Object.values(costsByStage).sort((a, b) => {
    // Sort by pipeline order
    const order = ["planning", "scripting", "metadata", "audio", "avatar", "broll", "assembly"];
    return order.indexOf(a.stage) - order.indexOf(b.stage);
  });

  const totalCost = stageEntries.reduce((sum, s) => sum + s.cost, 0);
  const totalTokens = stageEntries.reduce((sum, s) => sum + s.tokens, 0);

  const formatCost = (cost: number): string => {
    if (cost === 0) return "$0.00";
    if (cost < 0.01) return `$${cost.toFixed(4)}`;
    return `$${cost.toFixed(2)}`;
  };

  const formatTokens = (tokens: number): string => {
    if (tokens === 0) return "0";
    if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
    if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k`;
    return tokens.toString();
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Estimated Cost</CardTitle>
          <span className="text-xs text-gray-400">Internal tracking only</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Total summary */}
          <div className="flex items-center justify-between pb-3 border-b border-gray-200">
            <span className="text-sm font-medium text-gray-700">Total</span>
            <div className="text-right">
              <div className="text-lg font-semibold text-gray-900">
                {formatCost(totalCost)}
              </div>
              {totalTokens > 0 && (
                <div className="text-xs text-gray-500">
                  {formatTokens(totalTokens)} tokens
                </div>
              )}
            </div>
          </div>

          {/* Per-stage breakdown */}
          <div className="space-y-2">
            {stageEntries.map((entry) => (
              <div
                key={entry.stage}
                className="flex items-center justify-between py-1"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">
                    {snakeToTitle(entry.stage)}
                  </span>
                  {entry.jobCount > 1 && (
                    <span className="text-xs text-gray-400">
                      ({entry.jobCount} jobs)
                    </span>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-sm text-gray-700">
                    {formatCost(entry.cost)}
                  </span>
                  {entry.tokens > 0 && (
                    <span className="text-xs text-gray-400 ml-2">
                      ({formatTokens(entry.tokens)} tok)
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Disclaimer */}
          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
            Estimates based on internal instrumentation. Actual provider charges may vary.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
