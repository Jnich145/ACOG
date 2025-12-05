"""
External API client integrations for ACOG.

This module provides clients for external services:
- OpenAI: Content generation (planning, scripting, metadata)
- ElevenLabs: Voice synthesis for narration
- HeyGen: Avatar video generation for talking heads
- Runway: AI video generation for B-roll
- Storage: S3/MinIO for media asset storage

All clients follow consistent patterns:
- Retry logic with exponential backoff
- Usage and cost tracking
- Comprehensive logging
- FastAPI dependency injection support
"""

# OpenAI client
from acog.integrations.openai_client import (
    CompletionResult,
    JsonCompletionResult,
    OpenAIClient,
    TokenUsage,
    get_openai_client,
)

# Base client classes and utilities
from acog.integrations.base_client import (
    BaseHTTPClient,
    MediaResult,
    SyncBaseHTTPClient,
    UsageMetrics,
)

# Storage client
from acog.integrations.storage_client import (
    StorageClient,
    UploadResult,
    get_storage_client,
)

# ElevenLabs voice synthesis
from acog.integrations.elevenlabs_client import (
    ElevenLabsClient,
    SpeechResult,
    Voice,
    VoiceSettings,
    get_elevenlabs_client,
)

# HeyGen avatar video
from acog.integrations.heygen_client import (
    Avatar,
    HeyGenClient,
    HeyGenVoice,
    VideoGenerationJob,
    VideoResult as HeyGenVideoResult,
    VideoSettings,
    VideoStatus,
    get_heygen_client,
)

# Runway video generation
from acog.integrations.runway_client import (
    AspectRatio,
    GenerationJob,
    GenerationSettings,
    GenerationStatus,
    RunwayClient,
    RunwayModel,
    VideoResult as RunwayVideoResult,
    get_runway_client,
)

__all__ = [
    # OpenAI
    "OpenAIClient",
    "get_openai_client",
    "CompletionResult",
    "JsonCompletionResult",
    "TokenUsage",
    # Base client
    "BaseHTTPClient",
    "SyncBaseHTTPClient",
    "MediaResult",
    "UsageMetrics",
    # Storage
    "StorageClient",
    "get_storage_client",
    "UploadResult",
    # ElevenLabs
    "ElevenLabsClient",
    "get_elevenlabs_client",
    "Voice",
    "VoiceSettings",
    "SpeechResult",
    # HeyGen
    "HeyGenClient",
    "get_heygen_client",
    "Avatar",
    "HeyGenVoice",
    "VideoGenerationJob",
    "HeyGenVideoResult",
    "VideoSettings",
    "VideoStatus",
    # Runway
    "RunwayClient",
    "get_runway_client",
    "AspectRatio",
    "GenerationJob",
    "GenerationSettings",
    "GenerationStatus",
    "RunwayModel",
    "RunwayVideoResult",
]
