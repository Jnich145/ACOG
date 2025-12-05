"""
Script generation service for ACOG episodes.

This service uses OpenAI to generate full video scripts from episode plans,
incorporating channel persona and style guide context. Scripts include
markers for avatar segments, voiceover, B-roll, and timing cues.
"""

import logging
import re
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


class CTAPlacement(BaseModel):
    """A call-to-action placement within the script."""

    model_config = ConfigDict(extra="forbid")

    placement: str = Field(
        description="Where in the video: intro, mid, outro, or specific timestamp"
    )
    text: str = Field(
        description="The CTA text content"
    )


class ScriptSegment(BaseModel):
    """A segment of the episode script with timing and production markers."""

    model_config = ConfigDict(extra="forbid")

    segment_type: str = Field(
        description="Type: AVATAR, VO (voiceover), BROLL, PAUSE"
    )
    text: str = Field(
        description="The text content for this segment"
    )
    duration_seconds: float = Field(
        description="Estimated duration in seconds",
        ge=0,
    )
    broll_description: str = Field(
        description="Description of B-roll to show during this segment (empty string if not applicable)"
    )
    tone_direction: str = Field(
        description="Tone/delivery direction: excited, serious, thoughtful, etc. (empty string if not specified)"
    )
    visual_notes: str = Field(
        description="Notes for visual presentation (empty string if none)"
    )


class ScriptSection(BaseModel):
    """A section of the script corresponding to a plan section."""

    model_config = ConfigDict(extra="forbid")

    section_title: str = Field(
        description="Title of this section"
    )
    # Note: No description on list[$ref] fields - OpenAI structured output doesn't allow it
    segments: list[ScriptSegment]
    total_duration_seconds: float = Field(
        description="Total duration of this section"
    )
    transition_text: str = Field(
        description="Transition text to the next section (empty string if last section)"
    )


class GeneratedScript(BaseModel):
    """
    Complete generated script for an episode.

    This schema is used as the response_format for OpenAI structured output.
    Note: Fields using nested models ($ref) cannot have 'description' per OpenAI's
    strict JSON schema requirements.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        description="Episode title"
    )
    hook_text: str = Field(
        description="The opening hook (first 5-15 seconds)"
    )
    hook_type: str = Field(
        description="The hook style used: question, statistic, story, provocative"
    )
    # Note: No description on $ref fields - OpenAI structured output doesn't allow it
    intro: ScriptSection
    main_sections: list[ScriptSection]
    conclusion: ScriptSection
    total_word_count: int = Field(
        description="Total word count of all spoken text"
    )
    estimated_duration_seconds: int = Field(
        description="Total estimated video duration in seconds"
    )
    speaking_pace_wpm: int = Field(
        description="Assumed speaking pace in words per minute (typically 150)"
    )
    # Note: No description on list[$ref] fields - OpenAI structured output doesn't allow it
    cta_placements: list[CTAPlacement]
    production_notes: str = Field(
        description="Notes for the production team (empty string if none)"
    )


# =============================================================================
# Script Service Result
# =============================================================================


@dataclass
class ScriptingResult:
    """Result from the scripting service."""

    script: GeneratedScript
    formatted_script: str
    usage: TokenUsage
    model_used: str
    generation_time_seconds: float
    word_count: int
    estimated_duration_seconds: int

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for storage."""
        return {
            "script": self.script.model_dump(),
            "formatted_script": self.formatted_script,
            "usage": self.usage.to_dict(),
            "model_used": self.model_used,
            "generation_time_seconds": self.generation_time_seconds,
            "word_count": self.word_count,
            "estimated_duration_seconds": self.estimated_duration_seconds,
        }


# =============================================================================
# Script Service
# =============================================================================


class ScriptService:
    """
    Service for generating video scripts from episode plans.

    This service takes an episode plan and produces a full script with:
    - [AVATAR: text] markers for on-camera host segments
    - [VO: text] markers for voiceover segments
    - [BROLL: description] markers for B-roll footage cues
    - [PAUSE: duration] markers for beats and pauses
    - Word count and duration estimates

    Example:
        ```python
        service = ScriptService(db_session)
        result = service.generate_script(
            episode_id=uuid,
            refinement_notes="Make the intro more punchy"
        )
        print(result.formatted_script)
        ```
    """

    # Average speaking rates for duration estimation
    SPEAKING_PACE_WPM = 150  # Words per minute for natural speech

    def __init__(
        self,
        db: Session,
        openai_client: OpenAIClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize the script service.

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
        Build the system prompt with channel persona and style guide.

        Args:
            channel: The channel context

        Returns:
            System prompt string
        """
        persona = channel.persona
        style_guide = channel.style_guide

        persona_section = ""
        if persona:
            persona_section = f"""
## Your Persona - Write AS This Character
Name: {persona.get('name', 'Content Creator')}
Background: {persona.get('background', 'Expert in the subject matter')}
Voice: {persona.get('voice', 'Professional and engaging')}
Values: {', '.join(persona.get('values', ['accuracy', 'engagement']))}

Write the script in first person, embodying this persona's unique voice and perspective.
"""

        style_section = ""
        if style_guide:
            do_rules = style_guide.get('do_rules', [])
            dont_rules = style_guide.get('dont_rules', [])

            style_section = f"""
## Writing Style
Tone: {style_guide.get('tone', 'conversational')}
Complexity: {style_guide.get('complexity', 'intermediate')}
Pacing: {style_guide.get('pacing', 'moderate')}
Humor level: {style_guide.get('humor_level', 'light')}

### Writing Rules - MUST FOLLOW:
{chr(10).join(f'- DO: {rule}' for rule in do_rules)}
{chr(10).join(f'- DO NOT: {rule}' for rule in dont_rules)}
"""

        return f"""You are an expert video script writer for YouTube. Your job is to transform episode plans into engaging, well-paced scripts that sound natural when spoken aloud.

{persona_section}
{style_section}

## Script Format Requirements

Your script MUST use these markers for production:

1. **[AVATAR: text]** - Host appears on camera speaking this text
2. **[VO: text]** - Voiceover only (host not on camera, B-roll or graphics shown)
3. **[BROLL: description]** - Describe B-roll/visuals to show (no spoken text)
4. **[PAUSE: seconds]** - Beat/pause for effect (e.g., [PAUSE: 2])

## Writing Guidelines

1. **Natural Speech**: Write for the ear, not the eye. Use contractions, conversational phrases, and natural rhythm.

2. **Pacing Variety**: Mix:
   - Avatar segments for personal connection and emphasis
   - Voiceover for information delivery while showing visuals
   - B-roll suggestions to enhance understanding
   - Strategic pauses for dramatic effect or processing time

3. **Hook Power**: The first 5-10 seconds must grab attention immediately.

4. **Clear Transitions**: Each section should flow naturally to the next.

5. **Value First**: Front-load value - viewers should learn something quickly.

6. **CTA Integration**: Weave calls-to-action naturally into the content.

7. **Retention Techniques**:
   - Pattern interrupts every 60-90 seconds
   - Questions to keep viewers engaged
   - Teases of what's coming ("In a moment, I'll show you...")
   - Clear signposting ("Here's the key insight...")

8. **Word Count**: Aim for ~150 words per minute of speaking time.

Generate complete, production-ready scripts that can be recorded directly."""

    def _build_scripting_prompt(
        self,
        plan: dict[str, Any],
        channel: Channel,
        refinement_notes: str | None = None,
    ) -> str:
        """
        Build the user prompt for script generation.

        Args:
            plan: The episode plan dict
            channel: Channel for context
            refinement_notes: Optional notes for refinement

        Returns:
            User prompt string
        """
        # Format plan sections for the prompt
        sections_text = ""
        for i, section in enumerate(plan.get("sections", []), 1):
            key_points = section.get("key_points", [])
            broll = section.get("broll_suggestions", [])
            sections_text += f"""
### Section {i}: {section.get('title', 'Untitled')}
Duration target: ~{section.get('duration_seconds', 120)} seconds
Tone: {section.get('tone', 'informative')}
Key points to cover:
{chr(10).join(f'- {point}' for point in key_points)}

B-roll suggestions:
{chr(10).join(f'- {b}' for b in broll)}
"""

        hooks_text = ""
        for hook in plan.get("hooks", []):
            hooks_text += f"""
- [{hook.get('type', 'general')}]: {hook.get('text', '')}
"""

        ctas_text = ""
        for cta in plan.get("calls_to_action", []):
            ctas_text += f"- {cta.get('placement', 'mid')}: {cta.get('text', '')}\n"

        prompt = f"""Transform this episode plan into a complete video script.

## Episode Plan

### Title
{plan.get('title_suggestion', 'Untitled Episode')}

### Topic Summary
{plan.get('topic_summary', 'No summary provided')}

### Target Audience
{plan.get('target_audience', 'General audience')}

### Available Hooks (choose the best one or combine)
{hooks_text}

### Introduction
{plan.get('intro', 'Standard introduction')}
Duration: ~{plan.get('intro_duration_seconds', 30)} seconds

### Content Sections
{sections_text}

### Conclusion
{plan.get('conclusion', 'Standard conclusion')}
Duration: ~{plan.get('conclusion_duration_seconds', 30)} seconds

### Key Facts to Include
{chr(10).join(f'- {fact}' for fact in plan.get('key_facts', []))}

### Calls to Action
{ctas_text}

### Visual Style Notes
{plan.get('visual_style_notes', 'Standard visual approach')}

### Target Duration
Approximately {plan.get('estimated_total_duration_seconds', 600)} seconds ({plan.get('estimated_total_duration_seconds', 600) // 60} minutes)
"""

        if refinement_notes:
            prompt += f"""

## Refinement Requirements
{refinement_notes}
"""

        prompt += """

## Output Requirements

Generate a complete script with:
1. A powerful opening hook using the best option from the plan
2. All sections covered with proper markers ([AVATAR:], [VO:], [BROLL:], [PAUSE:])
3. Natural transitions between sections
4. CTAs integrated at the specified points
5. A satisfying conclusion that reinforces the main message
6. Accurate word count and duration estimates

The script should be immediately usable for recording."""

        return prompt

    def _format_script_text(self, script: GeneratedScript) -> str:
        """
        Format the generated script into a readable text format with markers.

        Args:
            script: The generated script object

        Returns:
            Formatted script string with production markers
        """
        lines = []
        lines.append(f"# {script.title}")
        lines.append("")
        lines.append(f"Total Duration: ~{script.estimated_duration_seconds // 60} minutes ({script.estimated_duration_seconds} seconds)")
        lines.append(f"Word Count: {script.total_word_count}")
        lines.append(f"Speaking Pace: {script.speaking_pace_wpm} WPM")
        lines.append("")
        lines.append("=" * 60)
        lines.append("")

        # Hook
        lines.append(f"## HOOK ({script.hook_type.upper()})")
        lines.append("")
        lines.append(f"[AVATAR: {script.hook_text}]")
        lines.append("")

        # Helper to format a section
        def format_section(section: ScriptSection, heading: str) -> list[str]:
            section_lines = []
            section_lines.append(f"## {heading}: {section.section_title}")
            section_lines.append(f"(~{int(section.total_duration_seconds)} seconds)")
            section_lines.append("")

            for segment in section.segments:
                if segment.tone_direction:
                    section_lines.append(f"  <!-- Tone: {segment.tone_direction} -->")

                if segment.segment_type == "AVATAR":
                    section_lines.append(f"[AVATAR: {segment.text}]")
                elif segment.segment_type == "VO":
                    section_lines.append(f"[VO: {segment.text}]")
                    if segment.broll_description:
                        section_lines.append(f"[BROLL: {segment.broll_description}]")
                elif segment.segment_type == "BROLL":
                    section_lines.append(f"[BROLL: {segment.broll_description or segment.text}]")
                elif segment.segment_type == "PAUSE":
                    section_lines.append(f"[PAUSE: {segment.duration_seconds}]")

                if segment.visual_notes:
                    section_lines.append(f"  <!-- Visual: {segment.visual_notes} -->")

                section_lines.append("")

            if section.transition_text:
                section_lines.append(f"  --> Transition: {section.transition_text}")
                section_lines.append("")

            return section_lines

        # Intro
        lines.extend(format_section(script.intro, "INTRO"))
        lines.append("-" * 40)
        lines.append("")

        # Main sections
        for i, section in enumerate(script.main_sections, 1):
            lines.extend(format_section(section, f"SECTION {i}"))
            lines.append("-" * 40)
            lines.append("")

        # Conclusion
        lines.extend(format_section(script.conclusion, "CONCLUSION"))

        # Production notes
        if script.production_notes:
            lines.append("=" * 60)
            lines.append("")
            lines.append("## PRODUCTION NOTES")
            lines.append("")
            lines.append(script.production_notes)

        # CTA placements
        if script.cta_placements:
            lines.append("")
            lines.append("## CTA PLACEMENTS")
            for cta in script.cta_placements:
                lines.append(f"- {cta.placement}: {cta.text}")

        return "\n".join(lines)

    def _count_words(self, script: GeneratedScript) -> int:
        """Count total spoken words in the script."""
        word_count = 0

        def count_section_words(section: ScriptSection) -> int:
            count = 0
            for segment in section.segments:
                if segment.segment_type in ["AVATAR", "VO"]:
                    count += len(segment.text.split())
            return count

        word_count += len(script.hook_text.split())
        word_count += count_section_words(script.intro)
        for section in script.main_sections:
            word_count += count_section_words(section)
        word_count += count_section_words(script.conclusion)

        return word_count

    def generate_script(
        self,
        episode_id: UUID,
        refinement_notes: str | None = None,
        job_id: UUID | None = None,
    ) -> ScriptingResult:
        """
        Generate a script from an episode's plan.

        This method:
        1. Fetches the episode with its plan
        2. Builds context from channel persona and style guide
        3. Generates a structured script using OpenAI
        4. Formats the script with production markers
        5. Stores results in episode.script and episode.script_metadata
        6. Updates job tracking if job_id provided

        Args:
            episode_id: The episode to generate a script for
            refinement_notes: Optional notes for script refinement
            job_id: Optional job ID for tracking

        Returns:
            ScriptingResult with the generated script and metadata

        Raises:
            NotFoundError: If episode not found
            ValidationError: If episode has no plan
            PipelineError: If script generation fails
        """
        start_time = datetime.now(UTC)

        # Fetch episode
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        if not episode.plan:
            raise ValidationError(
                message="Episode has no plan. Generate a plan first.",
                field="plan",
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
            user_prompt = self._build_scripting_prompt(
                plan=episode.plan,
                channel=channel,
                refinement_notes=refinement_notes,
            )

            logger.info(
                "Generating episode script",
                extra={
                    "episode_id": str(episode_id),
                    "channel_id": str(channel.id),
                    "has_refinement_notes": refinement_notes is not None,
                },
            )

            # Generate script using structured output
            script, usage = self._openai.complete_with_schema(
                messages=[{"role": "user", "content": user_prompt}],
                response_model=GeneratedScript,
                model=self._settings.openai_model_scripting,
                system_message=system_prompt,
                temperature=0.7,
                max_tokens=8000,
            )

            generation_time = (datetime.now(UTC) - start_time).total_seconds()

            # Format the script
            formatted_script = self._format_script_text(script)

            # Calculate word count
            word_count = self._count_words(script)

            # Create result
            result = ScriptingResult(
                script=script,
                formatted_script=formatted_script,
                usage=usage,
                model_used=self._settings.openai_model_scripting,
                generation_time_seconds=generation_time,
                word_count=word_count,
                estimated_duration_seconds=script.estimated_duration_seconds,
            )

            # Update episode
            episode.script = formatted_script
            episode.script_metadata = {
                "version": (episode.script_metadata.get("version", 0) + 1) if episode.script_metadata else 1,
                "word_count": word_count,
                "estimated_duration_seconds": script.estimated_duration_seconds,
                "speaking_pace_wpm": script.speaking_pace_wpm,
                "model_used": self._settings.openai_model_scripting,
                "generated_at": datetime.now(UTC).isoformat(),
                "tokens_used": usage.total_tokens,
                "cost_usd": float(usage.estimated_cost_usd),
                "structured_script": script.model_dump(),
            }

            episode.update_pipeline_stage(
                stage="scripting",
                status="completed",
                model_used=self._settings.openai_model_scripting,
                tokens_used=usage.total_tokens,
                cost_usd=float(usage.estimated_cost_usd),
                word_count=word_count,
            )

            # Update status if currently in PLANNING
            if episode.status == EpisodeStatus.PLANNING:
                episode.status = EpisodeStatus.SCRIPTING

            # Update job if provided
            if job:
                job.complete(result={
                    "script_generated": True,
                    "word_count": word_count,
                    "estimated_duration_seconds": script.estimated_duration_seconds,
                    "section_count": len(script.main_sections),
                })
                job.set_cost(float(usage.estimated_cost_usd), usage.total_tokens)

            self._db.commit()

            logger.info(
                "Episode script generated successfully",
                extra={
                    "episode_id": str(episode_id),
                    "word_count": word_count,
                    "duration_seconds": script.estimated_duration_seconds,
                    "tokens_used": usage.total_tokens,
                    "cost_usd": float(usage.estimated_cost_usd),
                    "generation_time_seconds": generation_time,
                },
            )

            return result

        except Exception as e:
            error_msg = str(e)
            episode.update_pipeline_stage(
                stage="scripting",
                status="failed",
                error=error_msg,
            )
            episode.last_error = error_msg

            if job:
                job.fail(error_msg)

            self._db.commit()

            logger.error(
                "Episode script generation failed",
                extra={
                    "episode_id": str(episode_id),
                    "error": error_msg,
                },
                exc_info=True,
            )

            raise PipelineError(
                message=f"Failed to generate episode script: {error_msg}",
                stage="scripting",
                episode_id=str(episode_id),
            ) from e

    def refine_script(
        self,
        episode_id: UUID,
        feedback: str,
        sections_to_revise: list[str] | None = None,
    ) -> ScriptingResult:
        """
        Refine an existing script based on feedback.

        Args:
            episode_id: The episode to refine the script for
            feedback: Specific feedback for revision
            sections_to_revise: Optional list of section titles to focus on

        Returns:
            ScriptingResult with the refined script
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        refinement_notes = f"Feedback for revision: {feedback}"
        if sections_to_revise:
            refinement_notes += f"\nFocus on these sections: {', '.join(sections_to_revise)}"

        if episode.script:
            refinement_notes += f"\n\nCurrent script for reference:\n{episode.script[:2000]}..."

        return self.generate_script(
            episode_id=episode_id,
            refinement_notes=refinement_notes,
        )

    def extract_voiceover_text(self, episode_id: UUID) -> str:
        """
        Extract only the voiceover/spoken text from a script.

        Useful for sending to voice synthesis services.

        Args:
            episode_id: The episode to extract text from

        Returns:
            Plain text of all spoken content
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        if not episode.script:
            raise ValidationError(
                message="Episode has no script",
                field="script",
            )

        # Extract text from markers
        script = episode.script

        # Find all AVATAR and VO markers
        avatar_pattern = r'\[AVATAR:\s*([^\]]+)\]'
        vo_pattern = r'\[VO:\s*([^\]]+)\]'

        avatar_matches = re.findall(avatar_pattern, script)
        vo_matches = re.findall(vo_pattern, script)

        # Combine in order (we need to preserve order from original script)
        combined_pattern = r'\[(AVATAR|VO):\s*([^\]]+)\]'
        all_matches = re.findall(combined_pattern, script)

        spoken_text = []
        for match_type, text in all_matches:
            spoken_text.append(text.strip())

        return "\n\n".join(spoken_text)


def get_script_service(db: Session) -> ScriptService:
    """
    Factory function to create a ScriptService.

    Use as a FastAPI dependency:
        ```python
        @router.post("/episodes/{id}/script")
        def create_script(
            id: UUID,
            service: ScriptService = Depends(get_script_service)
        ):
            return service.generate_script(id)
        ```

    Args:
        db: Database session from dependency injection

    Returns:
        Configured ScriptService instance
    """
    return ScriptService(db=db)
