"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface TitleOption {
  style: string;
  title: string;
  hook_element: string;
  seo_keywords: string[];
}

interface Chapter {
  title: string;
  timestamp_seconds: number;
}

interface SocialPost {
  text: string;
  hashtags: string[];
  platform: string;
}

interface ThumbnailPrompt {
  concept: string;
  emotion: string;
  main_visual: string;
  color_scheme: string;
  text_overlay: string;
  detailed_prompt: string;
}

interface EpisodeMetadata {
  tags?: string[];
  category?: string;
  chapters?: Chapter[];
  description?: string;
  description_short?: string;
  title_options?: TitleOption[];
  recommended_title?: string;
  social_posts?: SocialPost[];
  thumbnail_prompts?: ThumbnailPrompt[];
  recommended_thumbnail_index?: number;
  target_keywords?: string[];
  secondary_keywords?: string[];
  pinned_comment?: string;
  end_screen_cta?: string;
  cost_usd?: number;
  tokens_used?: number;
  model_used?: string;
  generated_at?: string;
}

interface MetadataViewerProps {
  metadata: Record<string, unknown>;
}

export function MetadataViewer({ metadata }: MetadataViewerProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [expandedThumbnail, setExpandedThumbnail] = useState<number | null>(null);

  const typedMetadata = metadata as EpisodeMetadata;

  const copyToClipboard = async (text: string, field: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const formatTimestamp = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, "0")}`;
  };

  const formatChaptersForYouTube = (): string => {
    if (!typedMetadata.chapters) return "";
    return typedMetadata.chapters
      .map((ch) => `${formatTimestamp(ch.timestamp_seconds)} ${ch.title}`)
      .join("\n");
  };

  const platformIcon = (platform: string) => {
    switch (platform.toLowerCase()) {
      case "twitter":
        return (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
          </svg>
        );
      case "linkedin":
        return (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
          </svg>
        );
      case "instagram":
        return (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
          </svg>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      {/* Recommended Title */}
      {typedMetadata.recommended_title && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recommended Title</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-2 p-3 bg-primary-50 rounded-lg border border-primary-100">
              <p className="font-medium text-gray-900">{typedMetadata.recommended_title}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => copyToClipboard(typedMetadata.recommended_title!, "title")}
              >
                {copiedField === "title" ? (
                  <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Title Options */}
      {typedMetadata.title_options && typedMetadata.title_options.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Title Options</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {typedMetadata.title_options.map((option, index) => (
              <div
                key={index}
                className={cn(
                  "p-3 rounded-lg border",
                  option.title === typedMetadata.recommended_title
                    ? "bg-primary-50 border-primary-200"
                    : "bg-gray-50 border-gray-100"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="default" className="capitalize text-xs">{option.style}</Badge>
                      {option.title === typedMetadata.recommended_title && (
                        <Badge variant="success" className="text-xs">Recommended</Badge>
                      )}
                    </div>
                    <p className="font-medium text-gray-900">{option.title}</p>
                    <p className="text-xs text-gray-500 mt-1">{option.hook_element}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(option.title, `title-${index}`)}
                  >
                    {copiedField === `title-${index}` ? (
                      <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Description */}
      {typedMetadata.description && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">YouTube Description</CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(typedMetadata.description!, "description")}
              >
                {copiedField === "description" ? "Copied!" : "Copy"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="bg-gray-50 rounded-md p-4 max-h-64 overflow-y-auto">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">
                {typedMetadata.description}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Chapters */}
      {typedMetadata.chapters && typedMetadata.chapters.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Video Chapters</CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(formatChaptersForYouTube(), "chapters")}
              >
                {copiedField === "chapters" ? "Copied!" : "Copy for YouTube"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {typedMetadata.chapters.map((chapter, index) => (
                <div key={index} className="flex items-center gap-3 py-1">
                  <span className="font-mono text-sm text-primary-600 w-12">
                    {formatTimestamp(chapter.timestamp_seconds)}
                  </span>
                  <span className="text-sm text-gray-700">{chapter.title}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tags & Keywords */}
      {(typedMetadata.tags || typedMetadata.target_keywords) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tags & Keywords</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {typedMetadata.target_keywords && typedMetadata.target_keywords.length > 0 && (
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Primary Keywords</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {typedMetadata.target_keywords.map((keyword, index) => (
                    <Badge key={index} variant="info">{keyword}</Badge>
                  ))}
                </div>
              </div>
            )}
            {typedMetadata.secondary_keywords && typedMetadata.secondary_keywords.length > 0 && (
              <div>
                <span className="text-xs text-gray-500 uppercase tracking-wide">Secondary Keywords</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {typedMetadata.secondary_keywords.map((keyword, index) => (
                    <Badge key={index} variant="default">{keyword}</Badge>
                  ))}
                </div>
              </div>
            )}
            {typedMetadata.tags && typedMetadata.tags.length > 0 && (
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 uppercase tracking-wide">Video Tags ({typedMetadata.tags.length})</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(typedMetadata.tags!.join(", "), "tags")}
                  >
                    {copiedField === "tags" ? "Copied!" : "Copy"}
                  </Button>
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {typedMetadata.tags.map((tag, index) => (
                    <span key={index} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Social Posts */}
      {typedMetadata.social_posts && typedMetadata.social_posts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Social Media Posts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {typedMetadata.social_posts.map((post, index) => (
              <div key={index} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500">{platformIcon(post.platform)}</span>
                    <span className="text-sm font-medium capitalize">{post.platform}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(post.text, `social-${index}`)}
                  >
                    {copiedField === `social-${index}` ? (
                      <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    )}
                  </Button>
                </div>
                <p className="text-sm text-gray-700">{post.text}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {post.hashtags.map((hashtag, hIndex) => (
                    <span key={hIndex} className="text-xs text-blue-600">{hashtag}</span>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Thumbnail Prompts */}
      {typedMetadata.thumbnail_prompts && typedMetadata.thumbnail_prompts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Thumbnail Ideas</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {typedMetadata.thumbnail_prompts.map((prompt, index) => (
              <div
                key={index}
                className={cn(
                  "p-3 rounded-lg border cursor-pointer transition-colors",
                  index === typedMetadata.recommended_thumbnail_index
                    ? "bg-primary-50 border-primary-200"
                    : "bg-gray-50 border-gray-100 hover:bg-gray-100"
                )}
                onClick={() => setExpandedThumbnail(expandedThumbnail === index ? null : index)}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="w-5 h-5 rounded-full bg-gray-200 text-gray-600 text-xs font-medium flex items-center justify-center">
                        {index + 1}
                      </span>
                      {index === typedMetadata.recommended_thumbnail_index && (
                        <Badge variant="success" className="text-xs">Recommended</Badge>
                      )}
                    </div>
                    <p className="text-sm font-medium text-gray-900">{prompt.concept}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span>Emotion: {prompt.emotion}</span>
                      <span>Colors: {prompt.color_scheme}</span>
                    </div>
                  </div>
                  <svg
                    className={cn(
                      "w-4 h-4 text-gray-400 transition-transform",
                      expandedThumbnail === index && "rotate-180"
                    )}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>

                {expandedThumbnail === index && (
                  <div className="mt-3 pt-3 border-t border-gray-200 space-y-2">
                    <div>
                      <span className="text-xs text-gray-500 uppercase tracking-wide">Text Overlay</span>
                      <p className="text-sm text-gray-700 font-medium">{prompt.text_overlay}</p>
                    </div>
                    <div>
                      <span className="text-xs text-gray-500 uppercase tracking-wide">Main Visual</span>
                      <p className="text-sm text-gray-700">{prompt.main_visual}</p>
                    </div>
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500 uppercase tracking-wide">Full Prompt</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(prompt.detailed_prompt, `thumbnail-${index}`);
                          }}
                        >
                          {copiedField === `thumbnail-${index}` ? "Copied!" : "Copy"}
                        </Button>
                      </div>
                      <p className="text-sm text-gray-600 bg-white p-2 rounded mt-1 border">
                        {prompt.detailed_prompt}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Engagement Elements */}
      {(typedMetadata.pinned_comment || typedMetadata.end_screen_cta) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Engagement Elements</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {typedMetadata.pinned_comment && (
              <div className="p-3 bg-yellow-50 rounded-lg border border-yellow-100">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-yellow-700 uppercase tracking-wide font-medium">Pinned Comment</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(typedMetadata.pinned_comment!, "pinned")}
                  >
                    {copiedField === "pinned" ? "Copied!" : "Copy"}
                  </Button>
                </div>
                <p className="text-sm text-gray-700">{typedMetadata.pinned_comment}</p>
              </div>
            )}
            {typedMetadata.end_screen_cta && (
              <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
                <span className="text-xs text-blue-700 uppercase tracking-wide font-medium">End Screen CTA</span>
                <p className="text-sm text-gray-700 mt-1">{typedMetadata.end_screen_cta}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Generation Info */}
      {(typedMetadata.cost_usd || typedMetadata.model_used || typedMetadata.generated_at) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Generation Info</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              {typedMetadata.model_used && (
                <>
                  <dt className="text-gray-500">Model</dt>
                  <dd className="text-gray-900 font-mono">{typedMetadata.model_used}</dd>
                </>
              )}
              {typedMetadata.tokens_used && (
                <>
                  <dt className="text-gray-500">Tokens</dt>
                  <dd className="text-gray-900">{typedMetadata.tokens_used.toLocaleString()}</dd>
                </>
              )}
              {typedMetadata.cost_usd && (
                <>
                  <dt className="text-gray-500">Cost</dt>
                  <dd className="text-gray-900">${typedMetadata.cost_usd.toFixed(4)}</dd>
                </>
              )}
              {typedMetadata.generated_at && (
                <>
                  <dt className="text-gray-500">Generated</dt>
                  <dd className="text-gray-900">{new Date(typedMetadata.generated_at).toLocaleString()}</dd>
                </>
              )}
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
