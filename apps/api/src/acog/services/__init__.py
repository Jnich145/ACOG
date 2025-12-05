"""
Business logic services for ACOG.

This module provides the core services for content generation:
- PlanningService: Generate episode plans from topics
- ScriptService: Generate video scripts from plans
- MetadataService: Generate SEO metadata from scripts

All services are designed to be injectable via FastAPI Depends().
"""

from acog.services.metadata import (
    MetadataResult,
    MetadataService,
    ThumbnailPrompt,
    TitleOption,
    VideoMetadata,
    get_metadata_service,
)
from acog.services.planning import (
    CallToAction,
    EpisodePlan,
    Hook,
    PlanningResult,
    PlanningService,
    Section,
    get_planning_service,
)
from acog.services.scripting import (
    GeneratedScript,
    ScriptingResult,
    ScriptSection,
    ScriptSegment,
    ScriptService,
    get_script_service,
)

__all__ = [
    # Planning Service
    "PlanningService",
    "get_planning_service",
    "PlanningResult",
    "EpisodePlan",
    "Hook",
    "Section",
    "CallToAction",
    # Script Service
    "ScriptService",
    "get_script_service",
    "ScriptingResult",
    "GeneratedScript",
    "ScriptSection",
    "ScriptSegment",
    # Metadata Service
    "MetadataService",
    "get_metadata_service",
    "MetadataResult",
    "VideoMetadata",
    "TitleOption",
    "ThumbnailPrompt",
]
