"""
Script revision service for interactive script editing.

This service handles iterative script revision based on user instructions,
enabling collaborative editing between the user and OpenAI.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from acog.core.config import Settings, get_settings
from acog.core.exceptions import NotFoundError, ValidationError
from acog.integrations.openai_client import OpenAIClient, TokenUsage, get_openai_client
from acog.models.channel import Channel
from acog.models.episode import Episode

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models for Structured Output
# =============================================================================


class ScriptRevision(BaseModel):
    """Result of a script revision request."""

    model_config = ConfigDict(extra="forbid")

    revised_script: str = Field(
        description="The complete revised script with all markers preserved"
    )
    changes_summary: str = Field(
        description="Brief summary of what was changed (2-3 sentences)"
    )
    sections_modified: list[str] = Field(
        description="List of section names that were modified"
    )


# =============================================================================
# Script Revision Result
# =============================================================================


@dataclass
class RevisionResult:
    """Result from script revision."""

    original_script: str
    revised_script: str
    changes_summary: str
    sections_modified: list[str]
    usage: TokenUsage
    model_used: str
    revision_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "original_script": self.original_script,
            "revised_script": self.revised_script,
            "changes_summary": self.changes_summary,
            "sections_modified": self.sections_modified,
            "usage": self.usage.to_dict(),
            "model_used": self.model_used,
            "revision_time_seconds": self.revision_time_seconds,
        }


# =============================================================================
# Script Revision Service
# =============================================================================


class ScriptRevisionService:
    """
    Service for iteratively revising scripts based on user instructions.

    This service enables a collaborative editing workflow where users can
    request specific changes to their script and the AI revises accordingly.

    Example:
        ```python
        service = ScriptRevisionService(db_session)
        result = service.revise_script(
            episode_id=uuid,
            instruction="Make the intro 30% shorter and more direct"
        )
        # User can then accept or discard the revision
        if user_accepts:
            service.accept_revision(episode_id, result.revised_script)
        ```
    """

    def __init__(
        self,
        db: Session,
        openai_client: OpenAIClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the script revision service."""
        self._db = db
        self._settings = settings or get_settings()
        self._openai = openai_client or get_openai_client(self._settings)

    def _build_revision_system_prompt(self, channel: Channel) -> str:
        """Build the system prompt for script revision."""
        persona = channel.persona
        style_guide = channel.style_guide

        persona_context = ""
        if persona:
            persona_context = f"""
The script is for a channel with this persona:
- Name: {persona.get('name', 'Content Creator')}
- Voice: {persona.get('voice', 'Professional and engaging')}
- Values: {', '.join(persona.get('values', []))}

Maintain this persona's voice when making revisions.
"""

        style_context = ""
        if style_guide:
            style_context = f"""
Style guidelines to follow:
- Tone: {style_guide.get('tone', 'conversational')}
- Complexity: {style_guide.get('complexity', 'intermediate')}
- Pacing: {style_guide.get('pacing', 'moderate')}
"""

        return f"""You are a professional script editor helping revise a video script.

{persona_context}
{style_context}

## Your Role

You receive:
1. A current script with production markers ([AVATAR:], [VO:], [BROLL:], [PAUSE:])
2. A specific instruction from the user about what to change

## Rules

1. **Preserve Format**: Keep ALL production markers intact. The format must remain:
   - [AVATAR: text] - Host on camera
   - [VO: text] - Voiceover
   - [BROLL: description] - B-roll cues
   - [PAUSE: seconds] - Pauses

2. **Targeted Changes**: Only modify what the user asks for. Don't rewrite unchanged sections.

3. **Maintain Consistency**: Keep the same overall structure unless asked to restructure.

4. **Natural Speech**: Ensure revised text still sounds natural when spoken aloud.

5. **Complete Output**: Return the ENTIRE revised script, not just the changed parts.

When making revisions, be precise and follow the user's instruction exactly."""

    def _build_revision_prompt(
        self,
        current_script: str,
        instruction: str,
    ) -> str:
        """Build the user prompt for revision."""
        return f"""## Current Script

```
{current_script}
```

## Revision Instruction

{instruction}

## Task

Revise the script according to the instruction above. Return the complete revised script with all markers preserved. Also provide a brief summary of what you changed."""

    def revise_script(
        self,
        episode_id: UUID,
        instruction: str,
    ) -> RevisionResult:
        """
        Revise a script based on user instruction.

        This generates a revision but does NOT automatically save it.
        The user must explicitly accept the revision to apply it.

        Args:
            episode_id: The episode to revise
            instruction: User's revision instruction

        Returns:
            RevisionResult with original and revised scripts

        Raises:
            NotFoundError: If episode not found
            ValidationError: If episode has no script
        """
        start_time = datetime.now(UTC)

        # Fetch episode
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        if not episode.script:
            raise ValidationError(
                message="Episode has no script to revise. Generate a script first.",
                field="script",
                details={"episode_id": str(episode_id)},
            )

        # Fetch channel for context
        channel = self._db.query(Channel).filter(
            Channel.id == episode.channel_id,
            Channel.deleted_at.is_(None),
        ).first()

        if not channel:
            raise NotFoundError("Channel", str(episode.channel_id))

        # Build prompts
        system_prompt = self._build_revision_system_prompt(channel)
        user_prompt = self._build_revision_prompt(
            current_script=episode.script,
            instruction=instruction,
        )

        logger.info(
            "Revising script",
            extra={
                "episode_id": str(episode_id),
                "instruction_length": len(instruction),
            },
        )

        # Generate revision using structured output
        revision, usage = self._openai.complete_with_schema(
            messages=[{"role": "user", "content": user_prompt}],
            response_model=ScriptRevision,
            model=self._settings.openai_model_scripting,
            system_message=system_prompt,
            temperature=0.5,  # Lower temperature for more focused edits
            max_tokens=8000,
        )

        revision_time = (datetime.now(UTC) - start_time).total_seconds()

        result = RevisionResult(
            original_script=episode.script,
            revised_script=revision.revised_script,
            changes_summary=revision.changes_summary,
            sections_modified=revision.sections_modified,
            usage=usage,
            model_used=self._settings.openai_model_scripting,
            revision_time_seconds=revision_time,
        )

        logger.info(
            "Script revision generated",
            extra={
                "episode_id": str(episode_id),
                "sections_modified": revision.sections_modified,
                "tokens_used": usage.total_tokens,
                "revision_time_seconds": revision_time,
            },
        )

        return result

    def accept_revision(
        self,
        episode_id: UUID,
        revised_script: str,
    ) -> dict[str, Any]:
        """
        Accept and save a script revision.

        This saves the current script to version history and applies the revision.

        Args:
            episode_id: The episode to update
            revised_script: The revised script to apply

        Returns:
            Dict with version info
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        # Store current script in version history
        script_metadata = episode.script_metadata or {}
        script_versions = script_metadata.get("versions", [])

        if episode.script:
            # Save current version before overwriting
            current_version = {
                "version": script_metadata.get("version", 1),
                "script": episode.script,
                "saved_at": datetime.now(UTC).isoformat(),
                "word_count": script_metadata.get("word_count"),
            }
            script_versions.append(current_version)

            # Keep only last 10 versions to prevent bloat
            if len(script_versions) > 10:
                script_versions = script_versions[-10:]

        # Calculate new word count
        import re
        avatar_pattern = r'\[AVATAR:\s*([^\]]+)\]'
        vo_pattern = r'\[VO:\s*([^\]]+)\]'
        combined_pattern = r'\[(AVATAR|VO):\s*([^\]]+)\]'
        all_matches = re.findall(combined_pattern, revised_script)
        word_count = sum(len(text.split()) for _, text in all_matches)

        # Update episode
        new_version = script_metadata.get("version", 0) + 1
        episode.script = revised_script
        episode.script_metadata = {
            **script_metadata,
            "version": new_version,
            "word_count": word_count,
            "last_revised_at": datetime.now(UTC).isoformat(),
            "versions": script_versions,
        }

        flag_modified(episode, "script_metadata")
        self._db.commit()

        logger.info(
            "Script revision accepted",
            extra={
                "episode_id": str(episode_id),
                "new_version": new_version,
                "word_count": word_count,
            },
        )

        return {
            "version": new_version,
            "word_count": word_count,
            "previous_versions_count": len(script_versions),
        }

    def get_script_versions(self, episode_id: UUID) -> list[dict[str, Any]]:
        """
        Get version history for an episode's script.

        Args:
            episode_id: The episode ID

        Returns:
            List of version records
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        script_metadata = episode.script_metadata or {}
        versions = script_metadata.get("versions", [])

        # Add current version
        if episode.script:
            current = {
                "version": script_metadata.get("version", 1),
                "script": episode.script,
                "saved_at": script_metadata.get("last_revised_at") or script_metadata.get("generated_at"),
                "word_count": script_metadata.get("word_count"),
                "is_current": True,
            }
            return versions + [current]

        return versions

    def restore_version(
        self,
        episode_id: UUID,
        version_number: int,
    ) -> dict[str, Any]:
        """
        Restore a previous script version.

        Args:
            episode_id: The episode ID
            version_number: The version to restore

        Returns:
            Dict with restoration info
        """
        episode = self._db.query(Episode).filter(
            Episode.id == episode_id,
            Episode.deleted_at.is_(None),
        ).first()

        if not episode:
            raise NotFoundError("Episode", str(episode_id))

        script_metadata = episode.script_metadata or {}
        versions = script_metadata.get("versions", [])

        # Find the version
        target_version = None
        for v in versions:
            if v.get("version") == version_number:
                target_version = v
                break

        if not target_version:
            raise ValidationError(
                message=f"Version {version_number} not found",
                field="version_number",
            )

        # Accept the restored version (which will save current to history)
        return self.accept_revision(episode_id, target_version["script"])


def get_script_revision_service(db: Session) -> ScriptRevisionService:
    """Factory function to create a ScriptRevisionService."""
    return ScriptRevisionService(db=db)
