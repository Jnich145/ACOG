"""
Planning service for ACOG episode content planning.

This service uses OpenAI to generate structured episode plans from topics,
incorporating channel persona and style guide context.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from acog.core.config import Settings, get_settings
from acog.core.exceptions import NotFoundError, PipelineError, ValidationError
from acog.integrations.openai_client import OpenAIClient, TokenUsage, get_openai_client
from acog.models.channel import Channel
from acog.models.episode import Episode
from acog.models.enums import EpisodeStatus, JobStatus
from acog.models.job import Job

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Structured Output
# =============================================================================


class Hook(BaseModel):
    """An attention-grabbing hook for the video opening."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        description="Type of hook: question, statistic, story, provocative, or visual"
    )
    text: str = Field(
        description="The hook content - what the host will say or what will be shown"
    )
    explanation: str = Field(
        description="Why this hook works for this topic and audience"
    )


class Section(BaseModel):
    """A content section within the episode."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Section title/heading")
    key_points: list[str] = Field(
        description="Main points to cover in this section (3-5 points)"
    )
    duration_seconds: int = Field(
        description="Estimated duration in seconds",
        ge=30,
        le=600,
    )
    broll_suggestions: list[str] = Field(
        description="Visual/B-roll suggestions for this section"
    )
    transition_to_next: str = Field(
        description="How to transition to the next section (empty string if last section)"
    )
    tone: str = Field(
        description="Tone for this section: informative, excited, serious, playful, etc."
    )
    source_references: list[str] = Field(
        description="Sources or references to cite in this section (empty list if none)"
    )


class CallToAction(BaseModel):
    """A call-to-action for the video."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        description="Type: subscribe, like, comment, link, merchandise, other"
    )
    placement: str = Field(
        description="When to show: intro, mid, outro, or specific timestamp"
    )
    text: str = Field(description="The CTA content")
    visual_cue: str = Field(
        description="Visual element to accompany the CTA (empty string if not applicable)"
    )


class EpisodePlan(BaseModel):
    """
    Complete structured plan for an episode.

    This schema is used as the response_format for OpenAI structured output.
    """

    model_config = ConfigDict(extra="forbid")

    title_suggestion: str = Field(
        description="Suggested title for the episode"
    )
    topic_summary: str = Field(
        description="Brief summary of the topic and angle (1-2 sentences)"
    )
    target_audience: str = Field(
        description="Description of who this content is for"
    )
    hooks: list[Hook] = Field(
        description="2-3 attention-grabbing hooks to choose from",
        min_length=2,
        max_length=4,
    )
    intro: str = Field(
        description="Introduction section after the hook - sets up the topic"
    )
    intro_duration_seconds: int = Field(
        description="Duration of intro in seconds",
        ge=15,
        le=120,
    )
    sections: list[Section] = Field(
        description="Main content sections (3-6 sections)",
        min_length=2,
        max_length=8,
    )
    conclusion: str = Field(
        description="How to wrap up the episode"
    )
    conclusion_duration_seconds: int = Field(
        description="Duration of conclusion in seconds",
        ge=15,
        le=90,
    )
    calls_to_action: list[CallToAction] = Field(
        description="Calls to action throughout the video",
        min_length=1,
        max_length=5,
    )
    estimated_total_duration_seconds: int = Field(
        description="Estimated total video duration in seconds"
    )
    key_facts: list[str] = Field(
        description="Important facts/statistics to include",
        min_length=3,
        max_length=10,
    )
    visual_style_notes: str = Field(
        description="Notes on visual style, graphics, and B-roll approach"
    )
    research_notes: str = Field(
        description="Additional research notes or sources to verify (empty string if none)"
    )


# =============================================================================
# Planning Service Result
# =============================================================================


@dataclass
class PlanningResult:
    """Result from the planning service."""

    plan: EpisodePlan
    usage: TokenUsage
    model_used: str
    generation_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for storage."""
        return {
            "plan": self.plan.model_dump(),
            "usage": self.usage.to_dict(),
            "model_used": self.model_used,
            "generation_time_seconds": self.generation_time_seconds,
        }


# =============================================================================
# Planning Service
# =============================================================================


class PlanningService:
    """
    Service for generating episode plans using OpenAI.

    This service takes a topic, channel persona, and style guide to produce
    a structured episode plan with hooks, sections, key points, and B-roll
    suggestions.

    Example:
        ```python
        service = PlanningService(db_session)
        result = await service.generate_plan(
            episode_id=uuid,
            topic="Black holes and time dilation",
            additional_context="Focus on recent discoveries"
        )
        ```
    """

    def __init__(
        self,
        db: Session,
        openai_client: OpenAIClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize the planning service.

        Args:
            db: SQLAlchemy database session
            openai_client: Optional OpenAI client (creates one if not provided)
            settings: Optional settings instance
        """
        self._db = db
        self._settings = settings or get_settings()
        self._openai = openai_client or get_openai_client(self._settings)

    def _build_system_prompt(self, channel: Channel) -> str:
        """
        Build the system prompt with channel persona and style guide.

        Args:
            channel: The channel to build context for

        Returns:
            System prompt string
        """
        persona = channel.persona
        style_guide = channel.style_guide

        persona_section = ""
        if persona:
            persona_section = f"""
## Your Persona
You are {persona.get('name', 'a content creator')}.
Background: {persona.get('background', 'Expert content creator')}
Voice: {persona.get('voice', 'Professional and engaging')}
Values: {', '.join(persona.get('values', ['accuracy', 'engagement']))}
Expertise areas: {', '.join(persona.get('expertise', []))}
"""

        style_section = ""
        if style_guide:
            do_rules = style_guide.get('do_rules', [])
            dont_rules = style_guide.get('dont_rules', [])
            target_length = style_guide.get('video_length_target') or {}

            style_section = f"""
## Content Style Guide
Tone: {style_guide.get('tone', 'conversational')}
Complexity level: {style_guide.get('complexity', 'intermediate')}
Pacing: {style_guide.get('pacing', 'moderate')}
Humor level: {style_guide.get('humor_level', 'light')}
Target video length: {target_length.get('min_minutes', 8)}-{target_length.get('max_minutes', 15)} minutes

### Do:
{chr(10).join(f'- {rule}' for rule in do_rules) if do_rules else '- Create engaging, informative content'}

### Do Not:
{chr(10).join(f'- {rule}' for rule in dont_rules) if dont_rules else '- Avoid clickbait or sensationalism'}
"""

        return f"""You are an expert content planner for YouTube videos. Your job is to create comprehensive, structured episode plans that will guide script writers and video producers.

{persona_section}
{style_section}

## Your Task
Create a detailed episode plan that includes:
1. Multiple hook options to grab viewer attention in the first 5-10 seconds
2. A clear introduction that sets up the topic
3. Well-organized content sections with key points and B-roll suggestions
4. A satisfying conclusion that summarizes and provides value
5. Strategic calls-to-action placed throughout the video
6. Visual style notes to guide production

## Planning Principles
- Start with the most compelling angle or hook
- Structure content for maximum retention (front-load value)
- Include variety in pacing and presentation style
- Suggest B-roll that enhances understanding, not just fills time
- Plan for natural CTA placement that doesn't feel forced
- Ensure each section flows logically to the next
- Balance entertainment with information

Create plans that would result in videos people actually want to watch and share."""

    def _build_planning_prompt(
        self,
        topic: str,
        channel: Channel,
        target_duration_minutes: int | None = None,
        additional_context: str | None = None,
    ) -> str:
        """
        Build the user prompt for episode planning.

        Args:
            topic: The episode topic
            channel: The channel (for target duration defaults)
            target_duration_minutes: Optional specific target duration
            additional_context: Additional context or requirements

        Returns:
            User prompt string
        """
        # Get target duration from channel style guide if not specified
        if target_duration_minutes is None:
            style = channel.style_guide or {}
            length_target = style.get('video_length_target') or {}
            min_mins = length_target.get('min_minutes', 8)
            max_mins = length_target.get('max_minutes', 15)
            target_duration_minutes = (min_mins + max_mins) // 2

        prompt = f"""Create a detailed episode plan for the following topic:

## Topic
{topic}

## Target Duration
Approximately {target_duration_minutes} minutes ({target_duration_minutes * 60} seconds)

## Channel Niche
{channel.niche or 'General education/entertainment'}
"""

        if additional_context:
            prompt += f"""
## Additional Context/Requirements
{additional_context}
"""

        prompt += """
## Output Requirements
Generate a complete episode plan with:
- At least 2-3 hook options (different styles)
- Clear intro (15-60 seconds)
- 3-6 content sections with specific key points and B-roll ideas
- Conclusion that summarizes and delivers value
- 2-3 calls-to-action placed strategically
- Key facts/statistics to include
- Visual style notes for the production team

Make the plan specific and actionable - script writers should be able to follow it directly."""

        return prompt

    def generate_plan(
        self,
        episode_id: UUID,
        topic: str,
        target_duration_minutes: int | None = None,
        additional_context: str | None = None,
        job_id: UUID | None = None,
    ) -> PlanningResult:
        """
        Generate an episode plan for a given topic.

        This method:
        1. Fetches the episode and channel information
        2. Builds context from channel persona and style guide
        3. Generates a structured plan using OpenAI
        4. Stores the result in the episode's plan field
        5. Updates job tracking if job_id provided

        Args:
            episode_id: The episode to generate a plan for
            topic: The topic/idea for the episode
            target_duration_minutes: Optional target video length
            additional_context: Additional requirements or context
            job_id: Optional job ID for tracking

        Returns:
            PlanningResult with the generated plan and usage info

        Raises:
            NotFoundError: If episode or channel not found
            PipelineError: If plan generation fails
            ValidationError: If topic is empty or invalid
        """
        if not topic or not topic.strip():
            raise ValidationError(
                message="Topic cannot be empty",
                field="topic",
            )

        start_time = datetime.now(UTC)

        # Fetch episode with channel
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

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
            user_prompt = self._build_planning_prompt(
                topic=topic,
                channel=channel,
                target_duration_minutes=target_duration_minutes,
                additional_context=additional_context,
            )

            logger.info(
                "Generating episode plan",
                extra={
                    "episode_id": str(episode_id),
                    "channel_id": str(channel.id),
                    "topic": topic[:100],
                },
            )

            # Generate plan using structured output
            plan, usage = self._openai.complete_with_schema(
                messages=[{"role": "user", "content": user_prompt}],
                response_model=EpisodePlan,
                model=self._settings.openai_model_planning,
                system_message=system_prompt,
                temperature=0.7,
                max_tokens=4000,
            )

            generation_time = (datetime.now(UTC) - start_time).total_seconds()

            # Create result
            result = PlanningResult(
                plan=plan,
                usage=usage,
                model_used=self._settings.openai_model_planning,
                generation_time_seconds=generation_time,
            )

            # Update episode
            episode.plan = plan.model_dump()
            episode.title = episode.title or plan.title_suggestion
            episode.update_pipeline_stage(
                stage="planning",
                status="completed",
                model_used=self._settings.openai_model_planning,
                tokens_used=usage.total_tokens,
                cost_usd=float(usage.estimated_cost_usd),
            )

            # Update status if still in IDEA state
            if episode.status == EpisodeStatus.IDEA:
                episode.status = EpisodeStatus.PLANNING

            # Update job if provided
            if job:
                job.complete(result={
                    "plan_generated": True,
                    "estimated_duration_seconds": plan.estimated_total_duration_seconds,
                    "section_count": len(plan.sections),
                })
                job.set_cost(float(usage.estimated_cost_usd), usage.total_tokens)

            self._db.commit()

            logger.info(
                "Episode plan generated successfully",
                extra={
                    "episode_id": str(episode_id),
                    "duration_seconds": plan.estimated_total_duration_seconds,
                    "section_count": len(plan.sections),
                    "tokens_used": usage.total_tokens,
                    "cost_usd": float(usage.estimated_cost_usd),
                    "generation_time_seconds": generation_time,
                },
            )

            return result

        except Exception as e:
            # Update episode pipeline state on failure
            error_msg = str(e)
            episode.update_pipeline_stage(
                stage="planning",
                status="failed",
                error=error_msg,
            )
            episode.last_error = error_msg

            # Update job on failure
            if job:
                job.fail(error_msg)

            self._db.commit()

            logger.error(
                "Episode plan generation failed",
                extra={
                    "episode_id": str(episode_id),
                    "error": error_msg,
                },
                exc_info=True,
            )

            raise PipelineError(
                message=f"Failed to generate episode plan: {error_msg}",
                stage="planning",
                episode_id=str(episode_id),
            ) from e

    def regenerate_plan(
        self,
        episode_id: UUID,
        feedback: str | None = None,
        keep_sections: list[str] | None = None,
    ) -> PlanningResult:
        """
        Regenerate a plan with optional feedback for refinement.

        Args:
            episode_id: The episode to regenerate the plan for
            feedback: Feedback on what to change
            keep_sections: Section titles to preserve

        Returns:
            PlanningResult with the new plan
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        # Get original topic from idea
        topic = episode.idea.get("topic") or episode.title

        additional_context = ""
        if episode.plan:
            additional_context = f"Previous plan summary: {episode.plan.get('topic_summary', '')}\n"

        if feedback:
            additional_context += f"Feedback/changes requested: {feedback}\n"

        if keep_sections:
            additional_context += f"Sections to keep or build upon: {', '.join(keep_sections)}"

        return self.generate_plan(
            episode_id=episode_id,
            topic=topic,
            additional_context=additional_context,
        )


def get_planning_service(db: Session) -> PlanningService:
    """
    Factory function to create a PlanningService.

    Use as a FastAPI dependency:
        ```python
        @router.post("/episodes/{id}/plan")
        def create_plan(
            id: UUID,
            service: PlanningService = Depends(get_planning_service)
        ):
            return service.generate_plan(id, topic="...")
        ```

    Args:
        db: Database session from dependency injection

    Returns:
        Configured PlanningService instance
    """
    return PlanningService(db=db)
