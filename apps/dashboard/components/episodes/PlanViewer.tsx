"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface Hook {
  text: string;
  type: string;
  explanation: string;
}

interface Section {
  title: string;
  tone: string;
  key_points: string[];
  duration_seconds: number;
  broll_suggestions: string[];
  source_references?: string[];
  transition_to_next?: string;
}

interface CallToAction {
  text: string;
  type: string;
  placement: string;
  visual_cue?: string;
}

interface EpisodePlan {
  hooks?: Hook[];
  intro?: string;
  sections?: Section[];
  key_facts?: string[];
  conclusion?: string;
  topic_summary?: string;
  research_notes?: string;
  calls_to_action?: CallToAction[];
  target_audience?: string;
  title_suggestion?: string;
  visual_style_notes?: string;
  intro_duration_seconds?: number;
  conclusion_duration_seconds?: number;
  estimated_total_duration_seconds?: number;
}

interface PlanViewerProps {
  plan: Record<string, unknown>;
}

export function PlanViewer({ plan }: PlanViewerProps) {
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set([0]));

  const typedPlan = plan as EpisodePlan;

  const toggleSection = (index: number) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSections(newExpanded);
  };

  const formatDuration = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (minutes === 0) return `${secs}s`;
    if (secs === 0) return `${minutes}m`;
    return `${minutes}m ${secs}s`;
  };

  const totalDuration = typedPlan.estimated_total_duration_seconds ||
    (typedPlan.sections?.reduce((sum, s) => sum + (s.duration_seconds || 0), 0) || 0) +
    (typedPlan.intro_duration_seconds || 30) +
    (typedPlan.conclusion_duration_seconds || 30);

  return (
    <div className="space-y-4">
      {/* Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Episode Overview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {typedPlan.title_suggestion && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Suggested Title</span>
              <p className="font-medium text-gray-900">{typedPlan.title_suggestion}</p>
            </div>
          )}
          {typedPlan.topic_summary && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Topic Summary</span>
              <p className="text-sm text-gray-700">{typedPlan.topic_summary}</p>
            </div>
          )}
          {typedPlan.target_audience && (
            <div>
              <span className="text-xs text-gray-500 uppercase tracking-wide">Target Audience</span>
              <p className="text-sm text-gray-700">{typedPlan.target_audience}</p>
            </div>
          )}
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1">
              <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-gray-600">~{formatDuration(totalDuration)}</span>
            </div>
            {typedPlan.sections && (
              <div className="flex items-center gap-1">
                <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                </svg>
                <span className="text-gray-600">{typedPlan.sections.length} sections</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Hooks */}
      {typedPlan.hooks && typedPlan.hooks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Opening Hooks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {typedPlan.hooks.map((hook, index) => (
                <div key={index} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm text-gray-800 italic">{hook.text}</p>
                    <Badge variant="default" className="shrink-0 capitalize">
                      {hook.type}
                    </Badge>
                  </div>
                  {hook.explanation && (
                    <p className="text-xs text-gray-500 mt-2">{hook.explanation}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Intro */}
      {typedPlan.intro && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Introduction</CardTitle>
              {typedPlan.intro_duration_seconds && (
                <span className="text-xs text-gray-500">{formatDuration(typedPlan.intro_duration_seconds)}</span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{typedPlan.intro}</p>
          </CardContent>
        </Card>
      )}

      {/* Sections */}
      {typedPlan.sections && typedPlan.sections.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Content Sections</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-gray-100">
              {typedPlan.sections.map((section, index) => (
                <div key={index} className="border-l-2 border-transparent hover:border-primary-500">
                  <button
                    onClick={() => toggleSection(index)}
                    className="w-full px-6 py-3 flex items-center justify-between text-left hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-primary-100 text-primary-600 text-xs font-medium flex items-center justify-center">
                        {index + 1}
                      </span>
                      <span className="font-medium text-gray-900">{section.title}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-500">{formatDuration(section.duration_seconds)}</span>
                      <svg
                        className={cn(
                          "w-4 h-4 text-gray-400 transition-transform",
                          expandedSections.has(index) && "rotate-180"
                        )}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>

                  {expandedSections.has(index) && (
                    <div className="px-6 pb-4 space-y-3">
                      {/* Key Points */}
                      {section.key_points && section.key_points.length > 0 && (
                        <div>
                          <span className="text-xs text-gray-500 uppercase tracking-wide">Key Points</span>
                          <ul className="mt-1 space-y-1">
                            {section.key_points.map((point, pIndex) => (
                              <li key={pIndex} className="text-sm text-gray-700 flex items-start gap-2">
                                <span className="text-primary-500 mt-1">•</span>
                                {point}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* B-Roll Suggestions */}
                      {section.broll_suggestions && section.broll_suggestions.length > 0 && (
                        <div>
                          <span className="text-xs text-gray-500 uppercase tracking-wide">B-Roll Suggestions</span>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {section.broll_suggestions.map((broll, bIndex) => (
                              <span key={bIndex} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-purple-50 text-purple-700">
                                {broll}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Transition */}
                      {section.transition_to_next && (
                        <div className="pt-2 border-t border-gray-100">
                          <span className="text-xs text-gray-500 uppercase tracking-wide">Transition</span>
                          <p className="text-sm text-gray-600 italic mt-1">"{section.transition_to_next}"</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Key Facts */}
      {typedPlan.key_facts && typedPlan.key_facts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Key Facts</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {typedPlan.key_facts.map((fact, index) => (
                <li key={index} className="flex items-start gap-2 text-sm text-gray-700">
                  <svg className="w-4 h-4 text-green-500 mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  {fact}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Conclusion */}
      {typedPlan.conclusion && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Conclusion</CardTitle>
              {typedPlan.conclusion_duration_seconds && (
                <span className="text-xs text-gray-500">{formatDuration(typedPlan.conclusion_duration_seconds)}</span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{typedPlan.conclusion}</p>
          </CardContent>
        </Card>
      )}

      {/* Calls to Action */}
      {typedPlan.calls_to_action && typedPlan.calls_to_action.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Calls to Action</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {typedPlan.calls_to_action.map((cta, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded-md">
                  <div className="flex items-center gap-2">
                    <Badge variant="info" className="capitalize">{cta.type}</Badge>
                    <span className="text-sm text-gray-700">{cta.text}</span>
                  </div>
                  <span className="text-xs text-gray-500 capitalize">{cta.placement}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Research Notes */}
      {typedPlan.research_notes && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Research Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-600 bg-yellow-50 p-3 rounded-md border border-yellow-100">
              {typedPlan.research_notes}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
