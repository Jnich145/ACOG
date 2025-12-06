"""
Metadata generation service for ACOG episodes.

This service uses OpenAI to generate SEO-optimized video metadata
including titles, descriptions, tags, and thumbnail prompts.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from acog.core.config import Settings, get_settings
from acog.core.exceptions import NotFoundError, PipelineError, ValidationError
from acog.integrations.openai_client import OpenAIClient, TokenUsage, get_openai_client
from acog.models.channel import Channel
from acog.models.episode import Episode
from acog.models.enums import EpisodeStatus
from acog.models.job import Job

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Structured Output
# =============================================================================


class TitleOption(BaseModel):
    """A title option with analysis."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        description="The video title (max 100 characters)",
        max_length=100,
    )
    style: str = Field(
        description="Title style: curiosity, benefit, how-to, listicle, story, or news"
    )
    hook_element: str = Field(
        description="What makes this title clickable"
    )
    seo_keywords: list[str] = Field(
        description="Primary SEO keywords in this title"
    )


class ThumbnailPrompt(BaseModel):
    """A thumbnail concept/prompt for image generation."""

    model_config = ConfigDict(extra="forbid")

    concept: str = Field(
        description="Brief description of the thumbnail concept"
    )
    main_visual: str = Field(
        description="Primary visual element"
    )
    text_overlay: str = Field(
        description="Text to overlay on thumbnail, max 4 words (empty string if none)"
    )
    emotion: str = Field(
        description="Emotional tone: curious, shocked, excited, thoughtful, etc."
    )
    color_scheme: str = Field(
        description="Suggested color palette"
    )
    detailed_prompt: str = Field(
        description="Detailed prompt for AI image generation (DALL-E, Midjourney)"
    )


class VideoChapter(BaseModel):
    """A chapter/timestamp marker in the video."""

    model_config = ConfigDict(extra="forbid")

    timestamp_seconds: int = Field(
        description="Timestamp in seconds from video start",
        ge=0,
    )
    title: str = Field(
        description="Chapter title (max 100 characters)",
        max_length=100,
    )


class SocialPost(BaseModel):
    """Social media post for promoting the video."""

    model_config = ConfigDict(extra="forbid")

    platform: str = Field(
        description="Platform: twitter, linkedin, instagram, threads"
    )
    text: str = Field(
        description="Post text content"
    )
    hashtags: list[str] = Field(
        description="Relevant hashtags (empty list if none)"
    )


class VideoMetadata(BaseModel):
    """
    Complete SEO metadata for a video.

    This schema is used as the response_format for OpenAI structured output.
    """

    model_config = ConfigDict(extra="forbid")

    title_options: list[TitleOption] = Field(
        description="3-5 title options, ranked by expected performance",
        min_length=3,
        max_length=5,
    )
    recommended_title: str = Field(
        description="The recommended title to use"
    )
    description: str = Field(
        description="Full video description (SEO-optimized, 200-500 words)"
    )
    description_short: str = Field(
        description="Short description for preview/excerpts (max 160 characters)",
        max_length=160,
    )
    tags: list[str] = Field(
        description="YouTube tags (15-30 relevant tags)",
        min_length=10,
        max_length=35,
    )
    category: str = Field(
        description="YouTube category: Education, Science & Technology, Entertainment, etc."
    )
    thumbnail_prompts: list[ThumbnailPrompt] = Field(
        description="2-3 thumbnail concepts",
        min_length=2,
        max_length=4,
    )
    recommended_thumbnail: int = Field(
        description="Index of recommended thumbnail (0-based)",
        ge=0,
    )
    chapters: list[VideoChapter] = Field(
        description="Video chapters with timestamps (empty list if none)"
    )
    end_screen_cta: str = Field(
        description="Call-to-action for end screen"
    )
    pinned_comment: str = Field(
        description="Suggested pinned comment"
    )
    social_posts: list[SocialPost] = Field(
        description="Social media posts for promotion (empty list if none)"
    )
    target_keywords: list[str] = Field(
        description="Primary SEO keywords targeted"
    )
    secondary_keywords: list[str] = Field(
        description="Secondary/long-tail keywords"
    )


# =============================================================================
# Metadata Service Result
# =============================================================================


@dataclass
class MetadataResult:
    """Result from the metadata service."""

    metadata: VideoMetadata
    usage: TokenUsage
    model_used: str
    generation_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for storage."""
        return {
            "metadata": self.metadata.model_dump(),
            "usage": self.usage.to_dict(),
            "model_used": self.model_used,
            "generation_time_seconds": self.generation_time_seconds,
        }


# =============================================================================
# Metadata Service
# =============================================================================


class MetadataService:
    """
    Service for generating video metadata using OpenAI.

    This service takes an episode script and generates:
    - Multiple title options with SEO analysis
    - SEO-optimized descriptions
    - Relevant tags
    - Thumbnail prompts for image generation
    - Video chapters
    - Social media posts

    Example:
        ```python
        service = MetadataService(db_session)
        result = service.generate_metadata(episode_id=uuid)
        print(result.metadata.recommended_title)
        print(result.metadata.tags)
        ```
    """

    def __init__(
        self,
        db: Session,
        openai_client: OpenAIClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize the metadata service.

        Args:
            db: SQLAlchemy database session
            openai_client: Optional OpenAI client
            settings: Optional settings instance
        """
        self._db = db
        self._settings = settings or get_settings()
        self._openai = openai_client or get_openai_client(self._settings)

    def _build_system_prompt(self, channel: Channel) -> str:
        """
        Build the system prompt with channel context.

        Args:
            channel: The channel for context

        Returns:
            System prompt string
        """
        persona = channel.persona
        style_guide = channel.style_guide

        niche_context = ""
        if channel.niche:
            niche_context = f"Content Niche: {channel.niche}"

        persona_context = ""
        if persona:
            persona_context = f"""
Channel Persona: {persona.get('name', 'Content Creator')}
Expertise: {', '.join(persona.get('expertise', []))}
Values: {', '.join(persona.get('values', []))}
"""

        style_context = ""
        if style_guide:
            dont_rules = style_guide.get('dont_rules', [])
            style_context = f"""
Content Style: {style_guide.get('tone', 'conversational')}
Audience Level: {style_guide.get('complexity', 'intermediate')}

Title/Thumbnail Rules to Follow:
{chr(10).join(f'- Avoid: {rule}' for rule in dont_rules if 'clickbait' in rule.lower() or 'title' in rule.lower())}
"""

        return f"""You are an expert YouTube SEO and content marketing specialist. Your job is to create metadata that maximizes video discoverability, click-through rates, and viewer retention.

{niche_context}
{persona_context}
{style_context}

## Your Expertise

1. **YouTube Algorithm**: You understand how YouTube's algorithm evaluates titles, descriptions, and tags for search and recommendation.

2. **CTR Optimization**: You craft titles and thumbnails that drive clicks without being clickbait.

3. **SEO Best Practices**: You optimize for both YouTube search and Google video search.

4. **Audience Psychology**: You understand what makes viewers click, watch, and subscribe.

## Title Guidelines

- Keep under 60 characters for full mobile display (max 100)
- Front-load keywords and compelling elements
- Use power words that trigger curiosity or emotion
- Avoid ALL CAPS (except strategic emphasis)
- No excessive punctuation or emoji spam
- Match the content - never mislead viewers

## Description Guidelines

- First 150 characters are crucial (shown in search)
- Include primary keywords naturally in first paragraph
- Add timestamps/chapters for longer videos
- Include relevant links and resources
- End with a call-to-action
- Use line breaks for readability

## Tag Guidelines

- Start with exact match keywords
- Include variations and related terms
- Mix broad and specific tags
- 15-30 tags is optimal
- Include common misspellings if relevant

## Thumbnail Prompt Guidelines

- Design for mobile (small screen visibility)
- High contrast, bold colors
- Minimal text (max 4 words)
- Face with emotion performs best
- Avoid clutter - focus on one main element

Generate metadata that would make you proud as a YouTube growth expert."""

    def _build_metadata_prompt(
        self,
        episode: Episode,
        channel: Channel,
    ) -> str:
        """
        Build the user prompt for metadata generation.

        Args:
            episode: The episode with script
            channel: Channel for context

        Returns:
            User prompt string
        """
        # Extract key info from script and plan
        script_excerpt = ""
        if episode.script:
            # Get first 2000 chars of script for context
            script_excerpt = episode.script[:2000]

        plan_info = ""
        if episode.plan:
            plan_info = f"""
Topic: {episode.plan.get('topic_summary', 'Not specified')}
Target Audience: {episode.plan.get('target_audience', 'General audience')}
Key Facts:
{chr(10).join(f'- {fact}' for fact in episode.plan.get('key_facts', [])[:5])}

Sections covered:
{chr(10).join(f'- {s.get("title", "Section")}' for s in episode.plan.get('sections', []))}
"""

        script_meta = episode.script_metadata or {}
        duration_info = ""
        if script_meta:
            duration_seconds = script_meta.get('estimated_duration_seconds', 0)
            duration_info = f"""
Video Duration: ~{duration_seconds // 60} minutes ({duration_seconds} seconds)
Word Count: {script_meta.get('word_count', 'Unknown')}
"""

        prompt = f"""Generate complete SEO metadata for this video.

## Video Information

Title (working): {episode.title or 'Untitled'}
Channel: {channel.name}
Niche: {channel.niche or 'General'}
{duration_info}

## Content Overview
{plan_info}

## Script Excerpt
{script_excerpt}

## Requirements

Generate:
1. **3-5 Title Options**: Different styles (curiosity, benefit, how-to, etc.)
2. **Recommended Title**: The best option for this content
3. **Full Description**: 200-500 words, SEO-optimized
4. **Short Description**: Max 160 chars for previews
5. **15-30 Tags**: Mix of broad and specific
6. **YouTube Category**: Best fit category
7. **2-3 Thumbnail Concepts**: With detailed prompts for AI generation
8. **Video Chapters**: Based on script sections
9. **Social Posts**: For Twitter/X, LinkedIn, Instagram
10. **Pinned Comment**: Engagement-driving comment
11. **Target Keywords**: Primary and secondary

Focus on:
- Discoverability (search optimization)
- Click-through rate (compelling titles/thumbnails)
- Watch time signals (accurate representation)
- Engagement hooks (comments, likes, shares)
"""

        return prompt

    def generate_metadata(
        self,
        episode_id: UUID,
        job_id: UUID | None = None,
    ) -> MetadataResult:
        """
        Generate SEO metadata for an episode.

        This method:
        1. Fetches the episode with its script
        2. Generates comprehensive metadata using OpenAI
        3. Stores results in episode.episode_meta
        4. Updates job tracking if job_id provided

        Args:
            episode_id: The episode to generate metadata for
            job_id: Optional job ID for tracking

        Returns:
            MetadataResult with the generated metadata

        Raises:
            NotFoundError: If episode not found
            ValidationError: If episode has no script
            PipelineError: If metadata generation fails
        """
        start_time = datetime.now(UTC)

        # Fetch episode
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        if not episode.script and not episode.plan:
            raise ValidationError(
                message="Episode has no script or plan. Generate content first.",
                field="script",
                details={"episode_id": str(episode_id)},
            )

        # Fetch channel
        channel = self._db.query(Channel).filter(
            Channel.id == episode.channel_id,
            Channel.deleted_at.is_(None),
        ).first()

        if not channel:
            raise NotFoundError("Channel", str(episode.channel_id))

        # Update job status if provided
        job: Job | None = None
        if job_id:
            job = self._db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.start()
                self._db.commit()

        try:
            # Build prompts
            system_prompt = self._build_system_prompt(channel)
            user_prompt = self._build_metadata_prompt(
                episode=episode,
                channel=channel,
            )

            logger.info(
                "Generating episode metadata",
                extra={
                    "episode_id": str(episode_id),
                    "channel_id": str(channel.id),
                },
            )

            # Generate metadata using structured output (using lighter model)
            metadata, usage = self._openai.complete_with_schema(
                messages=[{"role": "user", "content": user_prompt}],
                response_model=VideoMetadata,
                model=self._settings.openai_model_metadata,
                system_message=system_prompt,
                temperature=0.7,
                max_tokens=4000,
            )

            generation_time = (datetime.now(UTC) - start_time).total_seconds()

            # Create result
            result = MetadataResult(
                metadata=metadata,
                usage=usage,
                model_used=self._settings.openai_model_metadata,
                generation_time_seconds=generation_time,
            )

            # Update episode metadata field
            episode.episode_meta = {
                "title_options": [t.model_dump() for t in metadata.title_options],
                "recommended_title": metadata.recommended_title,
                "description": metadata.description,
                "description_short": metadata.description_short,
                "tags": metadata.tags,
                "category": metadata.category,
                "thumbnail_prompts": [t.model_dump() for t in metadata.thumbnail_prompts],
                "recommended_thumbnail_index": metadata.recommended_thumbnail,
                "chapters": [c.model_dump() for c in metadata.chapters],
                "end_screen_cta": metadata.end_screen_cta,
                "pinned_comment": metadata.pinned_comment,
                "social_posts": [s.model_dump() for s in metadata.social_posts],
                "target_keywords": metadata.target_keywords,
                "secondary_keywords": metadata.secondary_keywords,
                "model_used": self._settings.openai_model_metadata,
                "generated_at": datetime.now(UTC).isoformat(),
                "tokens_used": usage.total_tokens,
                "cost_usd": float(usage.estimated_cost_usd),
            }

            # Update title if not already set or if current is placeholder
            if not episode.title or episode.title == "Untitled":
                episode.title = metadata.recommended_title

            episode.update_pipeline_stage(
                stage="metadata",
                status="completed",
                model_used=self._settings.openai_model_metadata,
                tokens_used=usage.total_tokens,
                cost_usd=float(usage.estimated_cost_usd),
            )

            # Update job if provided
            if job:
                job.complete(result={
                    "metadata_generated": True,
                    "title_options_count": len(metadata.title_options),
                    "tags_count": len(metadata.tags),
                    "thumbnail_prompts_count": len(metadata.thumbnail_prompts),
                })
                job.set_cost(float(usage.estimated_cost_usd), usage.total_tokens)

            self._db.commit()

            logger.info(
                "Episode metadata generated successfully",
                extra={
                    "episode_id": str(episode_id),
                    "recommended_title": metadata.recommended_title[:50],
                    "tags_count": len(metadata.tags),
                    "tokens_used": usage.total_tokens,
                    "cost_usd": float(usage.estimated_cost_usd),
                    "generation_time_seconds": generation_time,
                },
            )

            return result

        except Exception as e:
            error_msg = str(e)
            episode.update_pipeline_stage(
                stage="metadata",
                status="failed",
                error=error_msg,
            )
            episode.last_error = error_msg

            if job:
                job.fail(error_msg)

            self._db.commit()

            logger.error(
                "Episode metadata generation failed",
                extra={
                    "episode_id": str(episode_id),
                    "error": error_msg,
                },
                exc_info=True,
            )

            raise PipelineError(
                message=f"Failed to generate episode metadata: {error_msg}",
                stage="metadata",
                episode_id=str(episode_id),
            ) from e

    def regenerate_titles(
        self,
        episode_id: UUID,
        style_preferences: list[str] | None = None,
        keyword_focus: list[str] | None = None,
    ) -> list[TitleOption]:
        """
        Regenerate title options with specific preferences.

        Args:
            episode_id: The episode ID
            style_preferences: Preferred title styles (curiosity, benefit, etc.)
            keyword_focus: Keywords to emphasize

        Returns:
            List of new title options
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        # Generate new metadata focused on titles
        result = self.generate_metadata(episode_id)
        return result.metadata.title_options

    def regenerate_thumbnail_prompts(
        self,
        episode_id: UUID,
        style_direction: str | None = None,
    ) -> list[ThumbnailPrompt]:
        """
        Regenerate thumbnail prompts with style direction.

        Args:
            episode_id: The episode ID
            style_direction: Style direction for thumbnails

        Returns:
            List of new thumbnail prompts
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        # Generate new metadata
        result = self.generate_metadata(episode_id)
        return result.metadata.thumbnail_prompts

    def get_export_metadata(self, episode_id: UUID) -> dict[str, Any]:
        """
        Get metadata formatted for YouTube upload.

        Args:
            episode_id: The episode ID

        Returns:
            Dictionary formatted for YouTube API
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        if not episode.episode_meta:
            raise ValidationError(
                message="Episode has no metadata. Generate metadata first.",
                field="metadata",
            )

        meta = episode.episode_meta

        # Format for YouTube API
        return {
            "snippet": {
                "title": meta.get("recommended_title", episode.title),
                "description": meta.get("description", ""),
                "tags": meta.get("tags", []),
                "categoryId": self._get_youtube_category_id(meta.get("category", "Education")),
            },
            "status": {
                "privacyStatus": "private",  # Default to private
                "madeForKids": False,
            },
            "acog_metadata": {
                "title_options": meta.get("title_options", []),
                "thumbnail_prompts": meta.get("thumbnail_prompts", []),
                "chapters": meta.get("chapters", []),
                "social_posts": meta.get("social_posts", []),
            },
        }

    def _get_youtube_category_id(self, category_name: str) -> str:
        """Map category name to YouTube category ID."""
        category_map = {
            "Education": "27",
            "Science & Technology": "28",
            "Entertainment": "24",
            "People & Blogs": "22",
            "News & Politics": "25",
            "Howto & Style": "26",
            "Film & Animation": "1",
            "Gaming": "20",
        }
        return category_map.get(category_name, "27")  # Default to Education


def get_metadata_service(db: Session) -> MetadataService:
    """
    Factory function to create a MetadataService.

    Use as a FastAPI dependency:
        ```python
        @router.post("/episodes/{id}/metadata")
        def create_metadata(
            id: UUID,
            service: MetadataService = Depends(get_metadata_service)
        ):
            return service.generate_metadata(id)
        ```

    Args:
        db: Database session from dependency injection

    Returns:
        Configured MetadataService instance
    """
    return MetadataService(db=db)
