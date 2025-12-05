# ACOG Phase 1 - REST API Contracts

**Version:** 1.1.0
**Last Updated:** 2025-12-05
**Status:** Approved for Implementation

---

## Table of Contents

1. [Overview](#1-overview)
2. [API Design Principles](#2-api-design-principles)
3. [Common Schemas](#3-common-schemas)
4. [Channel Endpoints](#4-channel-endpoints)
5. [Episode Endpoints](#5-episode-endpoints)
6. [Asset Endpoints](#6-asset-endpoints)
7. [Pipeline Endpoints](#7-pipeline-endpoints)
8. [Job Endpoints](#8-job-endpoints)
9. [Authentication Endpoints](#9-authentication-endpoints)
10. [System Endpoints](#10-system-endpoints)
11. [Error Handling](#11-error-handling)
12. [Pagination](#12-pagination)
13. [Authentication](#13-authentication)
14. [Rate Limiting](#14-rate-limiting)
15. [Versioning Strategy](#15-versioning-strategy)

---

## 1. Overview

This document defines the REST API contracts for ACOG Phase 1. These APIs serve as the contract between:

- **Next.js Dashboard** - Web-based management interface
- **Python CLI** - Command-line tool for power users
- **Future Integrations** - Pulse events, webhooks, third-party systems

### Base URL

```
Production: https://api.acog.io/api/v1
Development: http://localhost:8000/api/v1
```

### Content Type

All requests and responses use JSON:

```
Content-Type: application/json
Accept: application/json
```

---

## 2. API Design Principles

### 2.1 RESTful Resource Naming

- Use plural nouns for collections: `/channels`, `/episodes`
- Use nested resources for ownership: `/channels/{id}/episodes`
- Use verbs only for actions: `/episodes/{id}/pipeline/plan`

### 2.2 Consistent Response Structure

Every successful response follows this structure:

```json
{
  "data": { ... },
  "meta": { ... }
}
```

Every error response follows this structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": { ... }
  }
}
```

### 2.3 Idempotency

- All POST endpoints accept an optional `X-Idempotency-Key` header
- Duplicate requests with the same key return the original response
- Keys expire after 24 hours

### 2.4 Soft Deletes

- DELETE operations perform soft deletes (set `deleted_at` timestamp)
- Deleted resources are excluded from list queries by default
- Include `?include_deleted=true` to see deleted resources

---

## 3. Common Schemas

### 3.1 Timestamp Fields

All entities include these standard timestamp fields:

```yaml
TimestampFields:
  type: object
  properties:
    created_at:
      type: string
      format: date-time
      description: ISO 8601 timestamp when resource was created
      example: "2025-12-05T14:30:00Z"
    updated_at:
      type: string
      format: date-time
      description: ISO 8601 timestamp when resource was last updated
      example: "2025-12-05T15:45:00Z"
    deleted_at:
      type: string
      format: date-time
      nullable: true
      description: ISO 8601 timestamp when resource was soft-deleted
      example: null
```

### 3.2 UUID Format

All resource IDs use UUIDv4:

```yaml
UUID:
  type: string
  format: uuid
  pattern: ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
  example: "550e8400-e29b-41d4-a716-446655440000"
```

### 3.3 Pagination Metadata

```yaml
PaginationMeta:
  type: object
  properties:
    page:
      type: integer
      minimum: 1
      description: Current page number (1-indexed)
      example: 1
    page_size:
      type: integer
      minimum: 1
      maximum: 100
      description: Number of items per page
      example: 20
    total_items:
      type: integer
      minimum: 0
      description: Total number of items across all pages
      example: 157
    total_pages:
      type: integer
      minimum: 0
      description: Total number of pages
      example: 8
    has_next:
      type: boolean
      description: Whether there is a next page
      example: true
    has_prev:
      type: boolean
      description: Whether there is a previous page
      example: false
```

### 3.4 Persona Schema

```yaml
Persona:
  type: object
  required:
    - name
    - background
  properties:
    name:
      type: string
      minLength: 1
      maxLength: 100
      description: Display name for the persona
      example: "Dr. Nova Sterling"
    background:
      type: string
      maxLength: 2000
      description: Character background and expertise
      example: "Astrophysicist with 20 years of research experience..."
    voice:
      type: string
      maxLength: 500
      description: Description of speaking style and tone
      example: "Warm, authoritative, uses accessible analogies"
    values:
      type: array
      items:
        type: string
      description: Core values that guide content
      example: ["scientific accuracy", "accessibility", "wonder"]
    expertise:
      type: array
      items:
        type: string
      description: Areas of expertise
      example: ["cosmology", "astrophysics", "space exploration"]
```

### 3.5 Style Guide Schema

```yaml
StyleGuide:
  type: object
  properties:
    tone:
      type: string
      enum: [formal, conversational, casual, academic, enthusiastic]
      description: Overall tone of content
      example: "conversational"
    complexity:
      type: string
      enum: [beginner, intermediate, advanced, expert]
      description: Target audience complexity level
      example: "intermediate"
    pacing:
      type: string
      enum: [slow, moderate, fast]
      description: Content delivery speed
      example: "moderate"
    humor_level:
      type: string
      enum: [none, light, moderate, heavy]
      description: Amount of humor to include
      example: "light"
    video_length_target:
      type: object
      properties:
        min_minutes:
          type: integer
          minimum: 1
          example: 8
        max_minutes:
          type: integer
          maximum: 120
          example: 15
    do_rules:
      type: array
      items:
        type: string
      description: Things the content SHOULD do
      example: ["Use real-world analogies", "Include recent discoveries"]
    dont_rules:
      type: array
      items:
        type: string
      description: Things the content should AVOID
      example: ["Avoid jargon without explanation", "No clickbait titles"]
```

### 3.6 Voice Profile Schema

```yaml
VoiceProfile:
  type: object
  required:
    - provider
    - voice_id
  properties:
    provider:
      type: string
      enum: [elevenlabs, amazon_polly, google_tts]
      description: Voice synthesis provider
      example: "elevenlabs"
    voice_id:
      type: string
      description: Provider-specific voice identifier
      example: "pNInz6obpgDQGcFmaJgB"
    stability:
      type: number
      minimum: 0
      maximum: 1
      description: Voice stability setting (provider-specific)
      example: 0.75
    similarity_boost:
      type: number
      minimum: 0
      maximum: 1
      description: Similarity boost setting (provider-specific)
      example: 0.80
    style:
      type: number
      minimum: 0
      maximum: 1
      description: Style exaggeration (provider-specific)
      example: 0.35
```

### 3.7 Avatar Profile Schema

```yaml
AvatarProfile:
  type: object
  required:
    - provider
    - avatar_id
  properties:
    provider:
      type: string
      enum: [heygen, synthesia, d-id]
      description: Avatar video provider
      example: "heygen"
    avatar_id:
      type: string
      description: Provider-specific avatar identifier
      example: "avatar_abc123"
    background:
      type: string
      description: Background setting or scene
      example: "modern_office"
    framing:
      type: string
      enum: [closeup, medium, wide]
      description: Camera framing preference
      example: "medium"
    attire:
      type: string
      description: Avatar clothing/appearance setting
      example: "business_casual"
```

### 3.8 Pipeline State Schema

```yaml
PipelineState:
  type: object
  properties:
    current_stage:
      type: string
      enum: [idea, planning, scripting, script_review, metadata, audio, avatar, broll, assembly, upload, published]
      description: Current pipeline stage
      example: "scripting"
    overall_status:
      type: string
      enum: [pending, in_progress, completed, failed, cancelled]
      description: Overall pipeline status
      example: "in_progress"
    stages:
      type: object
      additionalProperties:
        $ref: '#/components/schemas/StageStatus'
      description: Status of each individual stage

StageStatus:
  type: object
  properties:
    status:
      type: string
      enum: [pending, queued, processing, completed, failed, skipped]
      example: "completed"
    started_at:
      type: string
      format: date-time
      nullable: true
      example: "2025-12-05T14:30:00Z"
    completed_at:
      type: string
      format: date-time
      nullable: true
      example: "2025-12-05T14:32:15Z"
    duration_seconds:
      type: number
      nullable: true
      example: 135.5
    error:
      type: string
      nullable: true
      description: Error message if stage failed
      example: null
    retry_count:
      type: integer
      minimum: 0
      example: 0
    output_ref:
      type: string
      nullable: true
      description: Reference to stage output (asset ID or S3 path)
      example: "asset_550e8400-e29b-41d4-a716-446655440000"
```

### 3.9 Episode Status Enum

```yaml
EpisodeStatus:
  type: string
  enum:
    - idea           # Initial idea captured
    - planning       # Planning stage in progress
    - scripting      # Script generation in progress
    - script_review  # Script ready for review/approval
    - production     # Media generation in progress
    - assembly       # Video assembly in progress
    - ready          # Ready for upload/publishing
    - publishing     # Upload in progress
    - published      # Successfully published
    - failed         # Pipeline failed
    - cancelled      # Manually cancelled
  description: Current status of the episode in the pipeline
```

### 3.10 Asset Schema

```yaml
Asset:
  type: object
  properties:
    id:
      type: string
      format: uuid
      description: Unique identifier for the asset
      example: "990e8400-e29b-41d4-a716-446655440004"
    episode_id:
      type: string
      format: uuid
      description: Parent episode identifier
      example: "880e8400-e29b-41d4-a716-446655440003"
    type:
      type: string
      enum: [plan, script, audio, avatar_video, broll, thumbnail, final_video, metadata]
      description: Type of asset
      example: "audio"
    filename:
      type: string
      maxLength: 255
      description: Original or generated filename
      example: "voiceover_v1.mp3"
    uri:
      type: string
      description: Storage URI (S3 path)
      example: "s3://acog-assets/episodes/880e8400/audio/voiceover_v1.mp3"
    mime_type:
      type: string
      description: MIME type of the asset
      example: "audio/mpeg"
    size_bytes:
      type: integer
      minimum: 0
      description: File size in bytes
      example: 2457600
    duration_seconds:
      type: number
      nullable: true
      description: Duration for audio/video assets
      example: 580.5
    provider:
      type: string
      enum: [openai, elevenlabs, heygen, synthesia, runway, pika, internal]
      description: Service that generated the asset
      example: "elevenlabs"
    version:
      type: integer
      minimum: 1
      description: Version number of this asset type
      example: 1
    metadata:
      type: object
      additionalProperties: true
      description: Provider-specific metadata
      example:
        model: "eleven_multilingual_v2"
        voice_id: "pNInz6obpgDQGcFmaJgB"
        stability: 0.75
    checksum:
      type: string
      description: MD5 or SHA256 checksum for integrity verification
      example: "d41d8cd98f00b204e9800998ecf8427e"
    created_at:
      type: string
      format: date-time
      example: "2025-12-05T15:00:00Z"
    deleted_at:
      type: string
      format: date-time
      nullable: true
      description: Soft delete timestamp
      example: null
```

### 3.11 Job Schema

```yaml
Job:
  type: object
  properties:
    id:
      type: string
      format: uuid
      description: Unique job identifier
      example: "job_aa0e8400-e29b-41d4-a716-446655440005"
    episode_id:
      type: string
      format: uuid
      description: Associated episode identifier
      example: "880e8400-e29b-41d4-a716-446655440003"
    stage:
      type: string
      enum: [planning, scripting, script_review, audio, avatar, broll, assembly, metadata]
      description: Pipeline stage this job is for
      example: "planning"
    status:
      type: string
      enum: [queued, processing, completed, failed, cancelled]
      description: Current job status
      example: "processing"
    progress:
      type: object
      nullable: true
      description: Progress information for long-running jobs
      properties:
        percent:
          type: integer
          minimum: 0
          maximum: 100
          example: 45
        current_step:
          type: string
          example: "generating_segments"
        steps_completed:
          type: integer
          example: 2
        steps_total:
          type: integer
          example: 5
    worker_id:
      type: string
      nullable: true
      description: ID of the worker processing this job
      example: "worker-01"
    params:
      type: object
      additionalProperties: true
      description: Parameters passed to the job
      example:
        model: "gpt-4.1"
        temperature: 0.7
    result:
      type: object
      nullable: true
      description: Job result on completion
      additionalProperties: true
    error_message:
      type: string
      nullable: true
      description: Error message if job failed
      example: null
    retry_count:
      type: integer
      minimum: 0
      description: Number of retry attempts
      example: 0
    cost_usd:
      type: number
      nullable: true
      description: Cost incurred by this job
      example: 0.35
    tokens_used:
      type: integer
      nullable: true
      description: Total tokens used (for LLM jobs)
      example: 2140
    queued_at:
      type: string
      format: date-time
      description: When the job was queued
      example: "2025-12-05T15:00:00Z"
    started_at:
      type: string
      format: date-time
      nullable: true
      description: When processing started
      example: "2025-12-05T15:00:05Z"
    completed_at:
      type: string
      format: date-time
      nullable: true
      description: When the job completed or failed
      example: null
    created_at:
      type: string
      format: date-time
      example: "2025-12-05T15:00:00Z"
    updated_at:
      type: string
      format: date-time
      example: "2025-12-05T15:00:05Z"
```

---

## 4. Channel Endpoints

### 4.1 Create Channel

Creates a new channel with persona and style guide configuration.

**Endpoint:** `POST /api/v1/channels`

**Request Headers:**
```
Content-Type: application/json
Authorization: Bearer <token>
X-Idempotency-Key: <optional-uuid>
```

**Request Body:**

```yaml
CreateChannelRequest:
  type: object
  required:
    - name
    - persona
  properties:
    name:
      type: string
      minLength: 1
      maxLength: 100
      description: Channel display name
      example: "Cosmic Horizons"
    description:
      type: string
      maxLength: 1000
      description: Channel description
      example: "Exploring the universe's greatest mysteries"
    niche:
      type: string
      maxLength: 100
      description: Content niche/category
      example: "cosmology"
    persona:
      $ref: '#/components/schemas/Persona'
    style_guide:
      $ref: '#/components/schemas/StyleGuide'
    voice_profile:
      $ref: '#/components/schemas/VoiceProfile'
    avatar_profile:
      $ref: '#/components/schemas/AvatarProfile'
    cadence:
      type: object
      properties:
        videos_per_week:
          type: integer
          minimum: 1
          maximum: 21
          example: 3
        preferred_days:
          type: array
          items:
            type: string
            enum: [monday, tuesday, wednesday, thursday, friday, saturday, sunday]
          example: ["monday", "wednesday", "friday"]
    youtube_channel_id:
      type: string
      description: YouTube channel ID for publishing
      example: "UC1234567890abcdef"
    is_active:
      type: boolean
      default: true
      description: Whether channel is active for content generation
```

**Example Request:**

```json
{
  "name": "Cosmic Horizons",
  "description": "Exploring the universe's greatest mysteries with cutting-edge science",
  "niche": "cosmology",
  "persona": {
    "name": "Dr. Nova Sterling",
    "background": "Astrophysicist with 20 years of research experience at major observatories. Passionate about making complex cosmic phenomena accessible to everyone.",
    "voice": "Warm and authoritative, uses accessible analogies, genuinely excited about discoveries",
    "values": ["scientific accuracy", "accessibility", "sense of wonder"],
    "expertise": ["cosmology", "astrophysics", "space exploration", "quantum physics"]
  },
  "style_guide": {
    "tone": "conversational",
    "complexity": "intermediate",
    "pacing": "moderate",
    "humor_level": "light",
    "video_length_target": {
      "min_minutes": 8,
      "max_minutes": 15
    },
    "do_rules": [
      "Use real-world analogies to explain complex concepts",
      "Include recent discoveries and research",
      "Reference visual demonstrations",
      "End with thought-provoking questions"
    ],
    "dont_rules": [
      "Avoid jargon without explanation",
      "No clickbait or sensationalism",
      "Don't oversimplify to the point of inaccuracy"
    ]
  },
  "voice_profile": {
    "provider": "elevenlabs",
    "voice_id": "pNInz6obpgDQGcFmaJgB",
    "stability": 0.75,
    "similarity_boost": 0.80
  },
  "avatar_profile": {
    "provider": "heygen",
    "avatar_id": "avatar_scientist_01",
    "background": "observatory_night",
    "framing": "medium"
  },
  "cadence": {
    "videos_per_week": 3,
    "preferred_days": ["monday", "wednesday", "friday"]
  },
  "is_active": true
}
```

**Response:** `201 Created`

```yaml
CreateChannelResponse:
  type: object
  properties:
    data:
      $ref: '#/components/schemas/Channel'
    meta:
      type: object
      properties:
        request_id:
          type: string
          format: uuid
```

**Example Response:**

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Cosmic Horizons",
    "description": "Exploring the universe's greatest mysteries with cutting-edge science",
    "niche": "cosmology",
    "persona": {
      "name": "Dr. Nova Sterling",
      "background": "Astrophysicist with 20 years of research experience at major observatories...",
      "voice": "Warm and authoritative, uses accessible analogies...",
      "values": ["scientific accuracy", "accessibility", "sense of wonder"],
      "expertise": ["cosmology", "astrophysics", "space exploration", "quantum physics"]
    },
    "style_guide": {
      "tone": "conversational",
      "complexity": "intermediate",
      "pacing": "moderate",
      "humor_level": "light",
      "video_length_target": {
        "min_minutes": 8,
        "max_minutes": 15
      },
      "do_rules": ["Use real-world analogies to explain complex concepts", "..."],
      "dont_rules": ["Avoid jargon without explanation", "..."]
    },
    "voice_profile": {
      "provider": "elevenlabs",
      "voice_id": "pNInz6obpgDQGcFmaJgB",
      "stability": 0.75,
      "similarity_boost": 0.80
    },
    "avatar_profile": {
      "provider": "heygen",
      "avatar_id": "avatar_scientist_01",
      "background": "observatory_night",
      "framing": "medium"
    },
    "cadence": {
      "videos_per_week": 3,
      "preferred_days": ["monday", "wednesday", "friday"]
    },
    "youtube_channel_id": null,
    "is_active": true,
    "episode_count": 0,
    "created_at": "2025-12-05T14:30:00Z",
    "updated_at": "2025-12-05T14:30:00Z",
    "deleted_at": null
  },
  "meta": {
    "request_id": "req_abc123"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 201 | Channel created successfully |
| 400 | Invalid request body (validation error) |
| 401 | Unauthorized (missing or invalid token) |
| 409 | Conflict (channel with same name exists) |
| 422 | Unprocessable entity (semantic validation error) |
| 500 | Internal server error |

---

### 4.2 List Channels

Retrieves a paginated list of all channels.

**Endpoint:** `GET /api/v1/channels`

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| page | integer | No | 1 | Page number (1-indexed) |
| page_size | integer | No | 20 | Items per page (max 100) |
| sort_by | string | No | created_at | Field to sort by: `name`, `created_at`, `updated_at`, `episode_count` |
| sort_order | string | No | desc | Sort order: `asc` or `desc` |
| is_active | boolean | No | - | Filter by active status |
| niche | string | No | - | Filter by niche (exact match) |
| search | string | No | - | Search in name and description |
| include_deleted | boolean | No | false | Include soft-deleted channels |

**Example Request:**

```
GET /api/v1/channels?page=1&page_size=10&is_active=true&sort_by=name&sort_order=asc
```

**Response:** `200 OK`

```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Cosmic Horizons",
      "description": "Exploring the universe's greatest mysteries",
      "niche": "cosmology",
      "persona": {
        "name": "Dr. Nova Sterling",
        "background": "...",
        "voice": "...",
        "values": ["..."],
        "expertise": ["..."]
      },
      "style_guide": { "..." },
      "voice_profile": { "..." },
      "avatar_profile": { "..." },
      "cadence": { "..." },
      "youtube_channel_id": "UC1234567890",
      "is_active": true,
      "episode_count": 42,
      "created_at": "2025-12-01T10:00:00Z",
      "updated_at": "2025-12-05T14:30:00Z",
      "deleted_at": null
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "Tech Pulse",
      "description": "Breaking down the latest in AI and technology",
      "niche": "technology",
      "persona": { "..." },
      "style_guide": { "..." },
      "voice_profile": { "..." },
      "avatar_profile": { "..." },
      "cadence": { "..." },
      "youtube_channel_id": null,
      "is_active": true,
      "episode_count": 28,
      "created_at": "2025-12-02T11:00:00Z",
      "updated_at": "2025-12-04T09:15:00Z",
      "deleted_at": null
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 2,
      "total_pages": 1,
      "has_next": false,
      "has_prev": false
    },
    "request_id": "req_def456"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid query parameters |
| 401 | Unauthorized |
| 500 | Internal server error |

---

### 4.3 Get Channel Details

Retrieves detailed information about a specific channel.

**Endpoint:** `GET /api/v1/channels/{channel_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| channel_id | uuid | Yes | Channel unique identifier |

**Example Request:**

```
GET /api/v1/channels/550e8400-e29b-41d4-a716-446655440000
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Cosmic Horizons",
    "description": "Exploring the universe's greatest mysteries with cutting-edge science",
    "niche": "cosmology",
    "persona": {
      "name": "Dr. Nova Sterling",
      "background": "Astrophysicist with 20 years of research experience...",
      "voice": "Warm and authoritative...",
      "values": ["scientific accuracy", "accessibility", "sense of wonder"],
      "expertise": ["cosmology", "astrophysics", "space exploration"]
    },
    "style_guide": {
      "tone": "conversational",
      "complexity": "intermediate",
      "pacing": "moderate",
      "humor_level": "light",
      "video_length_target": {
        "min_minutes": 8,
        "max_minutes": 15
      },
      "do_rules": ["..."],
      "dont_rules": ["..."]
    },
    "voice_profile": {
      "provider": "elevenlabs",
      "voice_id": "pNInz6obpgDQGcFmaJgB",
      "stability": 0.75,
      "similarity_boost": 0.80
    },
    "avatar_profile": {
      "provider": "heygen",
      "avatar_id": "avatar_scientist_01",
      "background": "observatory_night",
      "framing": "medium"
    },
    "cadence": {
      "videos_per_week": 3,
      "preferred_days": ["monday", "wednesday", "friday"]
    },
    "youtube_channel_id": "UC1234567890abcdef",
    "is_active": true,
    "episode_count": 42,
    "stats": {
      "total_episodes": 42,
      "published_episodes": 38,
      "failed_episodes": 2,
      "in_progress_episodes": 2,
      "avg_production_time_minutes": 22.5
    },
    "created_at": "2025-12-01T10:00:00Z",
    "updated_at": "2025-12-05T14:30:00Z",
    "deleted_at": null
  },
  "meta": {
    "request_id": "req_ghi789"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized |
| 404 | Channel not found |
| 500 | Internal server error |

---

### 4.4 Update Channel

Updates an existing channel. Supports partial updates (PATCH semantics via PUT).

**Endpoint:** `PUT /api/v1/channels/{channel_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| channel_id | uuid | Yes | Channel unique identifier |

**Request Body:**

```yaml
UpdateChannelRequest:
  type: object
  description: All fields optional - only provided fields are updated
  properties:
    name:
      type: string
      minLength: 1
      maxLength: 100
    description:
      type: string
      maxLength: 1000
    niche:
      type: string
      maxLength: 100
    persona:
      $ref: '#/components/schemas/Persona'
    style_guide:
      $ref: '#/components/schemas/StyleGuide'
    voice_profile:
      $ref: '#/components/schemas/VoiceProfile'
    avatar_profile:
      $ref: '#/components/schemas/AvatarProfile'
    cadence:
      type: object
      properties:
        videos_per_week:
          type: integer
        preferred_days:
          type: array
          items:
            type: string
    youtube_channel_id:
      type: string
    is_active:
      type: boolean
```

**Example Request:**

```json
{
  "style_guide": {
    "tone": "conversational",
    "complexity": "advanced",
    "pacing": "moderate",
    "humor_level": "moderate"
  },
  "cadence": {
    "videos_per_week": 4
  }
}
```

**Response:** `200 OK`

Returns the full updated channel object (same schema as GET response).

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Channel updated successfully |
| 400 | Invalid request body |
| 401 | Unauthorized |
| 404 | Channel not found |
| 409 | Conflict (name already exists) |
| 422 | Unprocessable entity |
| 500 | Internal server error |

---

### 4.5 Delete Channel (Soft Delete)

Soft deletes a channel. Sets `deleted_at` timestamp and marks as inactive.

**Endpoint:** `DELETE /api/v1/channels/{channel_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| channel_id | uuid | Yes | Channel unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| cascade_episodes | boolean | No | false | Also soft-delete all episodes |

**Example Request:**

```
DELETE /api/v1/channels/550e8400-e29b-41d4-a716-446655440000?cascade_episodes=true
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "deleted_at": "2025-12-05T16:00:00Z",
    "episodes_deleted": 42
  },
  "meta": {
    "request_id": "req_jkl012"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Channel soft-deleted successfully |
| 401 | Unauthorized |
| 404 | Channel not found |
| 409 | Conflict (has in-progress episodes and cascade=false) |
| 500 | Internal server error |

---

## 5. Episode Endpoints

### 5.1 Create Episode

Creates a new episode for a channel. Can be created from a manual idea or linked to a PulseEvent.

**Endpoint:** `POST /api/v1/channels/{channel_id}/episodes`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| channel_id | uuid | Yes | Parent channel identifier |

**Request Body:**

```yaml
CreateEpisodeRequest:
  type: object
  required:
    - title
    - idea_source
  properties:
    title:
      type: string
      minLength: 1
      maxLength: 200
      description: Working title for the episode
      example: "What Happens Inside a Black Hole?"
    idea_brief:
      type: string
      maxLength: 5000
      description: Initial idea description, context, and direction
      example: "Explore the theoretical physics of black hole interiors..."
    idea_source:
      type: string
      enum: [manual, pulse, series, repurpose]
      description: How this episode idea originated
      example: "manual"
    pulse_event_id:
      type: string
      format: uuid
      nullable: true
      description: Reference to PulseEvent if source is 'pulse'
      example: null
    series_info:
      type: object
      nullable: true
      description: Series information if part of a series
      properties:
        series_id:
          type: string
          format: uuid
        sequence_number:
          type: integer
          minimum: 1
    target_length_minutes:
      type: integer
      minimum: 1
      maximum: 120
      description: Target video length in minutes
      example: 12
    priority:
      type: string
      enum: [low, normal, high, urgent]
      default: normal
      description: Production priority
      example: "normal"
    tags:
      type: array
      items:
        type: string
        maxLength: 50
      maxItems: 20
      description: Tags for categorization and search
      example: ["black holes", "physics", "space"]
    notes:
      type: string
      maxLength: 2000
      description: Internal notes for production
      example: "Consider tie-in with recent Webb telescope discovery"
    auto_advance:
      type: boolean
      default: false
      description: Automatically advance through pipeline stages
      example: false
```

**Example Request (Manual Idea):**

```json
{
  "title": "What Happens Inside a Black Hole?",
  "idea_brief": "Explore the theoretical physics of black hole interiors, including the event horizon, singularity, spaghettification, and the information paradox. Target audience has basic physics understanding. Include recent research from 2024-2025.",
  "idea_source": "manual",
  "target_length_minutes": 12,
  "priority": "normal",
  "tags": ["black holes", "physics", "space", "theoretical physics"],
  "notes": "Consider tie-in with recent Webb telescope black hole discovery",
  "auto_advance": false
}
```

**Example Request (From Pulse Event):**

```json
{
  "title": "Why Is Everyone Talking About Quantum Entanglement?",
  "idea_brief": "Trending topic from Reddit r/science and Twitter. Multiple viral posts about recent quantum computing breakthrough. Opportunity to explain fundamentals while covering the news.",
  "idea_source": "pulse",
  "pulse_event_id": "770e8400-e29b-41d4-a716-446655440002",
  "target_length_minutes": 10,
  "priority": "high",
  "tags": ["quantum", "physics", "trending", "news"],
  "auto_advance": true
}
```

**Response:** `201 Created`

```yaml
CreateEpisodeResponse:
  type: object
  properties:
    data:
      $ref: '#/components/schemas/Episode'
    meta:
      type: object
      properties:
        request_id:
          type: string
```

**Example Response:**

```json
{
  "data": {
    "id": "880e8400-e29b-41d4-a716-446655440003",
    "channel_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "What Happens Inside a Black Hole?",
    "idea_brief": "Explore the theoretical physics of black hole interiors...",
    "idea_source": "manual",
    "pulse_event_id": null,
    "series_info": null,
    "status": "idea",
    "target_length_minutes": 12,
    "priority": "normal",
    "tags": ["black holes", "physics", "space", "theoretical physics"],
    "notes": "Consider tie-in with recent Webb telescope black hole discovery",
    "auto_advance": false,
    "plan": null,
    "script": null,
    "metadata": null,
    "pipeline_state": {
      "current_stage": "idea",
      "overall_status": "pending",
      "stages": {
        "planning": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "scripting": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "script_review": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "metadata": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "audio": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "avatar": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "broll": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "assembly": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "upload": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 }
      }
    },
    "cost_tracking": {
      "estimated_cost_usd": null,
      "actual_cost_usd": 0,
      "breakdown": {}
    },
    "assets": [],
    "created_at": "2025-12-05T14:30:00Z",
    "updated_at": "2025-12-05T14:30:00Z",
    "published_at": null,
    "deleted_at": null
  },
  "meta": {
    "request_id": "req_mno345"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 201 | Episode created successfully |
| 400 | Invalid request body |
| 401 | Unauthorized |
| 404 | Channel not found |
| 409 | Conflict (episode with same title exists in channel) |
| 422 | Unprocessable entity (e.g., invalid pulse_event_id) |
| 500 | Internal server error |

---

### 5.2 List Episodes

Retrieves a paginated list of episodes for a channel.

**Endpoint:** `GET /api/v1/channels/{channel_id}/episodes`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| channel_id | uuid | Yes | Parent channel identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| page | integer | No | 1 | Page number (1-indexed) |
| page_size | integer | No | 20 | Items per page (max 100) |
| sort_by | string | No | created_at | Sort field: `title`, `created_at`, `updated_at`, `status`, `priority` |
| sort_order | string | No | desc | Sort order: `asc` or `desc` |
| status | string | No | - | Filter by status (comma-separated for multiple) |
| priority | string | No | - | Filter by priority |
| idea_source | string | No | - | Filter by idea source |
| tags | string | No | - | Filter by tags (comma-separated, ANY match) |
| search | string | No | - | Search in title and idea_brief |
| include_deleted | boolean | No | false | Include soft-deleted episodes |
| created_after | string | No | - | Filter by creation date (ISO 8601) |
| created_before | string | No | - | Filter by creation date (ISO 8601) |

**Example Request:**

```
GET /api/v1/channels/550e8400-e29b-41d4-a716-446655440000/episodes?status=idea,planning,scripting&priority=high&page=1&page_size=10
```

**Response:** `200 OK`

```json
{
  "data": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "channel_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "What Happens Inside a Black Hole?",
      "idea_brief": "Explore the theoretical physics...",
      "idea_source": "manual",
      "status": "scripting",
      "target_length_minutes": 12,
      "priority": "high",
      "tags": ["black holes", "physics"],
      "pipeline_state": {
        "current_stage": "scripting",
        "overall_status": "in_progress",
        "stages": { "..." }
      },
      "cost_tracking": {
        "estimated_cost_usd": 2.50,
        "actual_cost_usd": 0.85,
        "breakdown": {}
      },
      "asset_count": 1,
      "created_at": "2025-12-05T14:30:00Z",
      "updated_at": "2025-12-05T15:45:00Z",
      "published_at": null,
      "deleted_at": null
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_items": 1,
      "total_pages": 1,
      "has_next": false,
      "has_prev": false
    },
    "filters_applied": {
      "status": ["idea", "planning", "scripting"],
      "priority": "high"
    },
    "request_id": "req_pqr678"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid query parameters |
| 401 | Unauthorized |
| 404 | Channel not found |
| 500 | Internal server error |

---

### 5.3 Get Episode Details

Retrieves detailed information about a specific episode, including full pipeline state and assets.

**Endpoint:** `GET /api/v1/episodes/{episode_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| include_assets | boolean | No | true | Include asset list in response |
| include_plan | boolean | No | true | Include full plan JSON |
| include_script | boolean | No | true | Include full script content |

**Example Request:**

```
GET /api/v1/episodes/880e8400-e29b-41d4-a716-446655440003?include_assets=true
```

**Response:** `200 OK`

```yaml
EpisodeDetailResponse:
  type: object
  properties:
    data:
      $ref: '#/components/schemas/EpisodeDetail'
    meta:
      type: object
```

**Example Response:**

```json
{
  "data": {
    "id": "880e8400-e29b-41d4-a716-446655440003",
    "channel_id": "550e8400-e29b-41d4-a716-446655440000",
    "channel": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Cosmic Horizons",
      "niche": "cosmology"
    },
    "title": "What Happens Inside a Black Hole?",
    "idea_brief": "Explore the theoretical physics of black hole interiors, including the event horizon, singularity, spaghettification, and the information paradox.",
    "idea_source": "manual",
    "pulse_event_id": null,
    "series_info": null,
    "status": "scripting",
    "target_length_minutes": 12,
    "priority": "normal",
    "tags": ["black holes", "physics", "space", "theoretical physics"],
    "notes": "Consider tie-in with recent Webb telescope black hole discovery",
    "auto_advance": false,
    "plan": {
      "hook": "What if you could fall into a black hole and survive long enough to see what's inside?",
      "intro": {
        "duration_seconds": 45,
        "content": "Brief overview of black holes and why their interiors fascinate scientists"
      },
      "sections": [
        {
          "title": "Crossing the Event Horizon",
          "duration_seconds": 120,
          "key_points": ["Point of no return", "Time dilation effects", "What you'd actually see"],
          "broll_suggestions": ["Animation of event horizon crossing", "Gravitational lensing visualization"]
        },
        {
          "title": "Spaghettification",
          "duration_seconds": 90,
          "key_points": ["Tidal forces explained", "Stellar vs supermassive differences"],
          "broll_suggestions": ["Tidal force animation", "Size comparison graphics"]
        },
        {
          "title": "The Singularity Question",
          "duration_seconds": 150,
          "key_points": ["What physics predicts", "Where physics breaks down", "Quantum gravity theories"],
          "broll_suggestions": ["Abstract singularity visualization", "Equation overlays"]
        },
        {
          "title": "The Information Paradox",
          "duration_seconds": 120,
          "key_points": ["Hawking radiation", "Information preservation", "Recent theoretical developments"],
          "broll_suggestions": ["Hawking radiation animation", "Timeline of theoretical developments"]
        }
      ],
      "conclusion": {
        "duration_seconds": 60,
        "content": "Recap and thought-provoking closing question",
        "cta": "Subscribe for more cosmic mysteries"
      },
      "total_estimated_duration_seconds": 585,
      "generated_at": "2025-12-05T15:00:00Z",
      "model_used": "gpt-4.1",
      "prompt_tokens": 1250,
      "completion_tokens": 890
    },
    "script": {
      "version": 1,
      "status": "draft",
      "full_text": "What if you could fall into a black hole and survive long enough to see what's inside? [PAUSE] Today, we're going on the ultimate cosmic journey...",
      "segments": [
        {
          "type": "avatar",
          "start_time": 0,
          "end_time": 45,
          "text": "What if you could fall into a black hole...",
          "tone": "intriguing",
          "notes": "Lean in slightly, raised eyebrow"
        },
        {
          "type": "voiceover",
          "start_time": 45,
          "end_time": 75,
          "text": "Black holes are regions of spacetime...",
          "broll_cue": "[BROLL: Animated black hole with accretion disk]"
        }
      ],
      "word_count": 1450,
      "estimated_duration_seconds": 580,
      "generated_at": "2025-12-05T15:30:00Z",
      "model_used": "gpt-4.1",
      "prompt_tokens": 2100,
      "completion_tokens": 1650
    },
    "metadata": null,
    "pipeline_state": {
      "current_stage": "scripting",
      "overall_status": "in_progress",
      "stages": {
        "planning": {
          "status": "completed",
          "started_at": "2025-12-05T14:45:00Z",
          "completed_at": "2025-12-05T15:00:00Z",
          "duration_seconds": 900,
          "error": null,
          "retry_count": 0,
          "output_ref": "plan_v1"
        },
        "scripting": {
          "status": "processing",
          "started_at": "2025-12-05T15:15:00Z",
          "completed_at": null,
          "duration_seconds": null,
          "error": null,
          "retry_count": 0,
          "output_ref": null
        },
        "script_review": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "metadata": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "audio": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "avatar": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "broll": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "assembly": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 },
        "upload": { "status": "pending", "started_at": null, "completed_at": null, "error": null, "retry_count": 0 }
      }
    },
    "cost_tracking": {
      "estimated_cost_usd": 2.50,
      "actual_cost_usd": 0.85,
      "breakdown": {
        "planning_openai": 0.35,
        "scripting_openai": 0.50
      }
    },
    "assets": [
      {
        "id": "990e8400-e29b-41d4-a716-446655440004",
        "episode_id": "880e8400-e29b-41d4-a716-446655440003",
        "type": "plan",
        "filename": "plan_v1.json",
        "uri": "s3://acog-assets/episodes/880e8400/plan_v1.json",
        "mime_type": "application/json",
        "size_bytes": 4520,
        "provider": "openai",
        "metadata": {
          "model": "gpt-4.1",
          "version": 1
        },
        "created_at": "2025-12-05T15:00:00Z"
      }
    ],
    "created_at": "2025-12-05T14:30:00Z",
    "updated_at": "2025-12-05T15:30:00Z",
    "published_at": null,
    "deleted_at": null
  },
  "meta": {
    "request_id": "req_stu901"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized |
| 404 | Episode not found |
| 500 | Internal server error |

---

### 5.4 Update Episode

Updates an existing episode. Supports partial updates.

**Endpoint:** `PUT /api/v1/episodes/{episode_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Request Body:**

```yaml
UpdateEpisodeRequest:
  type: object
  description: All fields optional - only provided fields are updated
  properties:
    title:
      type: string
      minLength: 1
      maxLength: 200
    idea_brief:
      type: string
      maxLength: 5000
    target_length_minutes:
      type: integer
      minimum: 1
      maximum: 120
    priority:
      type: string
      enum: [low, normal, high, urgent]
    tags:
      type: array
      items:
        type: string
    notes:
      type: string
      maxLength: 2000
    auto_advance:
      type: boolean
    script:
      type: object
      description: Manual script edits
      properties:
        full_text:
          type: string
          description: Updated script text
        segments:
          type: array
          description: Updated segments
    metadata:
      type: object
      description: Manual metadata edits
      properties:
        title_options:
          type: array
          items:
            type: string
        description:
          type: string
        tags:
          type: array
          items:
            type: string
```

**Example Request (Edit Script):**

```json
{
  "script": {
    "full_text": "What if you could fall into a black hole and survive long enough to see what's inside? [PAUSE] Today, we're embarking on the ultimate cosmic journey - one that will take us beyond the point of no return...",
    "segments": [
      {
        "type": "avatar",
        "start_time": 0,
        "end_time": 50,
        "text": "What if you could fall into a black hole and survive long enough to see what's inside?",
        "tone": "intriguing",
        "notes": "Lean in slightly, raised eyebrow, longer pause for effect"
      }
    ]
  },
  "notes": "Updated script intro for more dramatic effect"
}
```

**Response:** `200 OK`

Returns the full updated episode object (same schema as GET response).

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Episode updated successfully |
| 400 | Invalid request body |
| 401 | Unauthorized |
| 404 | Episode not found |
| 409 | Conflict (cannot edit during active pipeline stage) |
| 422 | Unprocessable entity |
| 500 | Internal server error |

---

### 5.5 Delete Episode (Soft Delete)

Soft deletes an episode. Cancels any in-progress pipeline stages.

**Endpoint:** `DELETE /api/v1/episodes/{episode_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| force | boolean | No | false | Force delete even if pipeline is in progress |

**Example Request:**

```
DELETE /api/v1/episodes/880e8400-e29b-41d4-a716-446655440003?force=true
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "880e8400-e29b-41d4-a716-446655440003",
    "deleted_at": "2025-12-05T16:00:00Z",
    "pipeline_cancelled": true,
    "assets_retained": true
  },
  "meta": {
    "request_id": "req_vwx234"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Episode soft-deleted successfully |
| 401 | Unauthorized |
| 404 | Episode not found |
| 409 | Conflict (pipeline in progress and force=false) |
| 500 | Internal server error |

---

## 6. Asset Endpoints

### 6.1 List Episode Assets

Retrieves a paginated list of assets for an episode, optionally filtered by type.

**Endpoint:** `GET /api/v1/episodes/{episode_id}/assets`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| page | integer | No | 1 | Page number (1-indexed) |
| page_size | integer | No | 20 | Items per page (max 100) |
| type | string | No | - | Filter by asset type (comma-separated for multiple) |
| provider | string | No | - | Filter by provider |
| sort_by | string | No | created_at | Sort field: `created_at`, `type`, `size_bytes` |
| sort_order | string | No | desc | Sort order: `asc` or `desc` |
| include_deleted | boolean | No | false | Include soft-deleted assets |

**Example Request:**

```
GET /api/v1/episodes/880e8400-e29b-41d4-a716-446655440003/assets?type=audio,avatar_video&sort_by=created_at&sort_order=desc
```

**Response:** `200 OK`

```json
{
  "data": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440004",
      "episode_id": "880e8400-e29b-41d4-a716-446655440003",
      "type": "audio",
      "filename": "voiceover_v1.mp3",
      "uri": "s3://acog-assets/episodes/880e8400/audio/voiceover_v1.mp3",
      "mime_type": "audio/mpeg",
      "size_bytes": 2457600,
      "duration_seconds": 580.5,
      "provider": "elevenlabs",
      "version": 1,
      "metadata": {
        "model": "eleven_multilingual_v2",
        "voice_id": "pNInz6obpgDQGcFmaJgB",
        "stability": 0.75
      },
      "checksum": "d41d8cd98f00b204e9800998ecf8427e",
      "created_at": "2025-12-05T15:30:00Z",
      "deleted_at": null
    },
    {
      "id": "990e8400-e29b-41d4-a716-446655440005",
      "episode_id": "880e8400-e29b-41d4-a716-446655440003",
      "type": "plan",
      "filename": "plan_v1.json",
      "uri": "s3://acog-assets/episodes/880e8400/plan_v1.json",
      "mime_type": "application/json",
      "size_bytes": 4520,
      "duration_seconds": null,
      "provider": "openai",
      "version": 1,
      "metadata": {
        "model": "gpt-4.1",
        "prompt_tokens": 1250,
        "completion_tokens": 890
      },
      "checksum": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
      "created_at": "2025-12-05T15:00:00Z",
      "deleted_at": null
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 2,
      "total_pages": 1,
      "has_next": false,
      "has_prev": false
    },
    "filters_applied": {
      "type": ["audio", "avatar_video"]
    },
    "request_id": "req_ast001"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid query parameters |
| 401 | Unauthorized |
| 404 | Episode not found |
| 500 | Internal server error |

---

### 6.2 Get Asset Details

Retrieves detailed information about a specific asset.

**Endpoint:** `GET /api/v1/assets/{asset_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| asset_id | uuid | Yes | Asset unique identifier |

**Example Request:**

```
GET /api/v1/assets/990e8400-e29b-41d4-a716-446655440004
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "episode": {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "title": "What Happens Inside a Black Hole?",
      "channel_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "type": "audio",
    "filename": "voiceover_v1.mp3",
    "uri": "s3://acog-assets/episodes/880e8400/audio/voiceover_v1.mp3",
    "mime_type": "audio/mpeg",
    "size_bytes": 2457600,
    "duration_seconds": 580.5,
    "provider": "elevenlabs",
    "version": 1,
    "metadata": {
      "model": "eleven_multilingual_v2",
      "voice_id": "pNInz6obpgDQGcFmaJgB",
      "stability": 0.75,
      "similarity_boost": 0.80,
      "style": 0.35,
      "generation_time_seconds": 45.2
    },
    "checksum": "d41d8cd98f00b204e9800998ecf8427e",
    "job_id": "job_dd0e8400-e29b-41d4-a716-446655440008",
    "created_at": "2025-12-05T15:30:00Z",
    "updated_at": "2025-12-05T15:30:00Z",
    "deleted_at": null
  },
  "meta": {
    "request_id": "req_ast002"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized |
| 404 | Asset not found |
| 500 | Internal server error |

---

### 6.3 Get Asset Download URL

Generates a signed download URL for an asset. The URL is valid for a limited time.

**Endpoint:** `GET /api/v1/assets/{asset_id}/download`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| asset_id | uuid | Yes | Asset unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| expires_in | integer | No | 3600 | URL expiration time in seconds (max 86400) |
| disposition | string | No | attachment | Content disposition: `attachment` or `inline` |

**Example Request:**

```
GET /api/v1/assets/990e8400-e29b-41d4-a716-446655440004/download?expires_in=7200&disposition=inline
```

**Response:** `200 OK`

```json
{
  "data": {
    "asset_id": "990e8400-e29b-41d4-a716-446655440004",
    "download_url": "https://acog-assets.s3.amazonaws.com/episodes/880e8400/audio/voiceover_v1.mp3?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
    "expires_at": "2025-12-05T17:30:00Z",
    "expires_in_seconds": 7200,
    "filename": "voiceover_v1.mp3",
    "mime_type": "audio/mpeg",
    "size_bytes": 2457600,
    "checksum": "d41d8cd98f00b204e9800998ecf8427e"
  },
  "meta": {
    "request_id": "req_ast003"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid query parameters (e.g., expires_in > 86400) |
| 401 | Unauthorized |
| 404 | Asset not found |
| 410 | Gone (asset has been permanently deleted from storage) |
| 500 | Internal server error |

---

### 6.4 Delete Asset (Soft Delete)

Soft deletes an asset. The asset file remains in storage but is marked as deleted.

**Endpoint:** `DELETE /api/v1/assets/{asset_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| asset_id | uuid | Yes | Asset unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| permanent | boolean | No | false | Permanently delete from storage (admin only) |

**Example Request:**

```
DELETE /api/v1/assets/990e8400-e29b-41d4-a716-446655440004
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "deleted_at": "2025-12-05T16:00:00Z",
    "storage_retained": true
  },
  "meta": {
    "request_id": "req_ast004"
  }
}
```

**Response (Permanent Delete):** `200 OK`

```json
{
  "data": {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "deleted_at": "2025-12-05T16:00:00Z",
    "storage_retained": false,
    "storage_deleted_at": "2025-12-05T16:00:01Z"
  },
  "meta": {
    "request_id": "req_ast005"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Asset soft-deleted successfully |
| 401 | Unauthorized |
| 403 | Forbidden (permanent delete requires admin role) |
| 404 | Asset not found |
| 409 | Conflict (asset is referenced by an active pipeline stage) |
| 500 | Internal server error |

---

## 7. Pipeline Endpoints

### 7.1 Trigger Planning Stage

Triggers the planning stage for an episode. Uses OpenAI to generate a structured episode plan.

**Endpoint:** `POST /api/v1/episodes/{episode_id}/pipeline/plan`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Request Body:**

```yaml
TriggerPlanRequest:
  type: object
  properties:
    model:
      type: string
      enum: [gpt-4.1, gpt-4.1-mini, gpt-4o]
      default: gpt-4.1
      description: OpenAI model to use for planning
    additional_context:
      type: string
      maxLength: 2000
      description: Additional context to include in the planning prompt
    override_persona:
      type: boolean
      default: false
      description: If true, allows planning without channel persona
    temperature:
      type: number
      minimum: 0
      maximum: 2
      default: 0.7
      description: Model temperature for creativity control
    async:
      type: boolean
      default: true
      description: If true, returns immediately with job ID. If false, waits for completion.
```

**Example Request:**

```json
{
  "model": "gpt-4.1",
  "additional_context": "Focus on recent 2024-2025 research. The audience recently watched our video on neutron stars, so we can reference that.",
  "temperature": 0.7,
  "async": true
}
```

**Response (Async):** `202 Accepted`

```json
{
  "data": {
    "job_id": "job_aa0e8400-e29b-41d4-a716-446655440005",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "stage": "planning",
    "status": "queued",
    "estimated_duration_seconds": 30,
    "queued_at": "2025-12-05T15:00:00Z"
  },
  "meta": {
    "request_id": "req_yza567",
    "poll_url": "/api/v1/episodes/880e8400-e29b-41d4-a716-446655440003/pipeline/status"
  }
}
```

**Response (Sync, async=false):** `200 OK`

```json
{
  "data": {
    "job_id": "job_aa0e8400-e29b-41d4-a716-446655440005",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "stage": "planning",
    "status": "completed",
    "started_at": "2025-12-05T15:00:00Z",
    "completed_at": "2025-12-05T15:00:28Z",
    "duration_seconds": 28,
    "result": {
      "plan_version": 1,
      "sections_count": 4,
      "estimated_duration_seconds": 585
    },
    "cost": {
      "prompt_tokens": 1250,
      "completion_tokens": 890,
      "total_tokens": 2140,
      "cost_usd": 0.35
    }
  },
  "meta": {
    "request_id": "req_yza567"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Planning completed (sync mode) |
| 202 | Planning job queued (async mode) |
| 400 | Invalid request body |
| 401 | Unauthorized |
| 404 | Episode not found |
| 409 | Conflict (planning already in progress or already completed) |
| 422 | Unprocessable (missing required data like channel persona) |
| 500 | Internal server error |
| 503 | Service unavailable (OpenAI API down) |

---

### 7.2 Trigger Script Generation

Triggers AI script generation based on the episode plan.

**Endpoint:** `POST /api/v1/episodes/{episode_id}/pipeline/script`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Request Body:**

```yaml
TriggerScriptRequest:
  type: object
  properties:
    model:
      type: string
      enum: [gpt-4.1, gpt-4.1-mini, gpt-4o]
      default: gpt-4.1
      description: OpenAI model to use for script generation
    include_qa_pass:
      type: boolean
      default: true
      description: Include QA/refinement pass after initial generation
    additional_instructions:
      type: string
      maxLength: 2000
      description: Additional instructions for script generation
    segment_types:
      type: array
      items:
        type: string
        enum: [avatar, voiceover, mixed]
      default: [avatar, voiceover]
      description: Types of segments to generate
    temperature:
      type: number
      minimum: 0
      maximum: 2
      default: 0.8
      description: Model temperature
    async:
      type: boolean
      default: true
```

**Example Request:**

```json
{
  "model": "gpt-4.1",
  "include_qa_pass": true,
  "additional_instructions": "Include a callback to our neutron star video when discussing stellar remnants",
  "segment_types": ["avatar", "voiceover"],
  "async": true
}
```

**Response:** `202 Accepted`

```json
{
  "data": {
    "job_id": "job_bb0e8400-e29b-41d4-a716-446655440006",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "stage": "scripting",
    "status": "queued",
    "estimated_duration_seconds": 60,
    "queued_at": "2025-12-05T15:05:00Z",
    "depends_on": {
      "planning": "completed"
    }
  },
  "meta": {
    "request_id": "req_bcd890",
    "poll_url": "/api/v1/episodes/880e8400-e29b-41d4-a716-446655440003/pipeline/status"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Script generation completed (sync mode) |
| 202 | Script generation job queued (async mode) |
| 400 | Invalid request body |
| 401 | Unauthorized |
| 404 | Episode not found |
| 409 | Conflict (scripting already in progress or plan not complete) |
| 422 | Unprocessable (planning stage not completed) |
| 500 | Internal server error |
| 503 | Service unavailable (OpenAI API down) |

---

### 7.3 Get Pipeline Status

Returns the current pipeline state for an episode, including all stage statuses.

**Endpoint:** `GET /api/v1/episodes/{episode_id}/pipeline/status`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| include_history | boolean | No | false | Include history of all runs for each stage |

**Example Request:**

```
GET /api/v1/episodes/880e8400-e29b-41d4-a716-446655440003/pipeline/status?include_history=true
```

**Response:** `200 OK`

```json
{
  "data": {
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "episode_title": "What Happens Inside a Black Hole?",
    "current_stage": "scripting",
    "overall_status": "in_progress",
    "progress_percent": 22,
    "stages": {
      "planning": {
        "status": "completed",
        "started_at": "2025-12-05T14:45:00Z",
        "completed_at": "2025-12-05T15:00:00Z",
        "duration_seconds": 900,
        "error": null,
        "retry_count": 0,
        "output_ref": "asset_990e8400-e29b-41d4-a716-446655440004",
        "cost_usd": 0.35
      },
      "scripting": {
        "status": "processing",
        "started_at": "2025-12-05T15:15:00Z",
        "completed_at": null,
        "duration_seconds": null,
        "error": null,
        "retry_count": 0,
        "output_ref": null,
        "cost_usd": null,
        "progress": {
          "current_step": "generating_segments",
          "steps_completed": 2,
          "steps_total": 5
        }
      },
      "script_review": {
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "error": null,
        "retry_count": 0
      },
      "metadata": {
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "error": null,
        "retry_count": 0
      },
      "audio": {
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "error": null,
        "retry_count": 0
      },
      "avatar": {
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "error": null,
        "retry_count": 0
      },
      "broll": {
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "error": null,
        "retry_count": 0
      },
      "assembly": {
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "error": null,
        "retry_count": 0
      },
      "upload": {
        "status": "pending",
        "started_at": null,
        "completed_at": null,
        "error": null,
        "retry_count": 0
      }
    },
    "active_jobs": [
      {
        "job_id": "job_bb0e8400-e29b-41d4-a716-446655440006",
        "stage": "scripting",
        "status": "processing",
        "worker_id": "worker-01",
        "started_at": "2025-12-05T15:15:00Z"
      }
    ],
    "total_cost_usd": 0.35,
    "estimated_remaining_cost_usd": 2.15,
    "estimated_completion_time": "2025-12-05T15:45:00Z",
    "history": [
      {
        "stage": "planning",
        "run_number": 1,
        "status": "completed",
        "started_at": "2025-12-05T14:45:00Z",
        "completed_at": "2025-12-05T15:00:00Z"
      }
    ]
  },
  "meta": {
    "request_id": "req_efg123"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized |
| 404 | Episode not found |
| 500 | Internal server error |

---

### 7.4 Retry Failed Stage

Retries a failed pipeline stage with optional parameter overrides.

**Endpoint:** `POST /api/v1/episodes/{episode_id}/pipeline/retry`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Request Body:**

```yaml
RetryStageRequest:
  type: object
  properties:
    stage:
      type: string
      enum: [planning, scripting, script_review, metadata, audio, avatar, broll, assembly, upload]
      description: Stage to retry (defaults to last failed stage)
    reset_downstream:
      type: boolean
      default: false
      description: Reset all stages after this one to pending
    override_params:
      type: object
      description: Parameters to override for the retry
      properties:
        model:
          type: string
        temperature:
          type: number
        additional_context:
          type: string
    async:
      type: boolean
      default: true
```

**Example Request:**

```json
{
  "stage": "scripting",
  "reset_downstream": true,
  "override_params": {
    "model": "gpt-4.1",
    "temperature": 0.6,
    "additional_context": "Previous attempt was too technical. Simplify the language."
  },
  "async": true
}
```

**Response:** `202 Accepted`

```json
{
  "data": {
    "job_id": "job_cc0e8400-e29b-41d4-a716-446655440007",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "stage": "scripting",
    "status": "queued",
    "retry_number": 2,
    "previous_error": "OpenAI API timeout after 60 seconds",
    "queued_at": "2025-12-05T16:00:00Z",
    "downstream_reset": ["script_review", "metadata", "audio", "avatar", "broll", "assembly", "upload"]
  },
  "meta": {
    "request_id": "req_hij456"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 202 | Retry job queued |
| 400 | Invalid request body |
| 401 | Unauthorized |
| 404 | Episode not found |
| 409 | Conflict (stage not in failed state or another job in progress) |
| 422 | Unprocessable (max retries exceeded) |
| 500 | Internal server error |

---

### 7.5 Cancel Pipeline

Cancels all in-progress pipeline stages for an episode.

**Endpoint:** `POST /api/v1/episodes/{episode_id}/pipeline/cancel`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Request Body:**

```yaml
CancelPipelineRequest:
  type: object
  properties:
    reason:
      type: string
      maxLength: 500
      description: Reason for cancellation
```

**Example Request:**

```json
{
  "reason": "Need to revise the episode direction based on new information"
}
```

**Response:** `200 OK`

```json
{
  "data": {
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "cancelled_jobs": [
      {
        "job_id": "job_bb0e8400-e29b-41d4-a716-446655440006",
        "stage": "scripting",
        "was_status": "processing"
      }
    ],
    "pipeline_status": "cancelled",
    "cancelled_at": "2025-12-05T16:05:00Z"
  },
  "meta": {
    "request_id": "req_klm789"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Pipeline cancelled |
| 401 | Unauthorized |
| 404 | Episode not found |
| 409 | Conflict (no active jobs to cancel) |
| 500 | Internal server error |

---

## 8. Job Endpoints

### 8.1 Get Job Status

Retrieves the current status and details of a specific job.

**Endpoint:** `GET /api/v1/jobs/{job_id}`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | uuid | Yes | Job unique identifier |

**Example Request:**

```
GET /api/v1/jobs/job_aa0e8400-e29b-41d4-a716-446655440005
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "job_aa0e8400-e29b-41d4-a716-446655440005",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "episode": {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "title": "What Happens Inside a Black Hole?",
      "channel_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "stage": "planning",
    "status": "completed",
    "progress": null,
    "worker_id": "worker-01",
    "params": {
      "model": "gpt-4.1",
      "temperature": 0.7,
      "additional_context": "Focus on recent 2024-2025 research."
    },
    "result": {
      "plan_version": 1,
      "sections_count": 4,
      "estimated_duration_seconds": 585,
      "output_asset_id": "990e8400-e29b-41d4-a716-446655440004"
    },
    "error_message": null,
    "retry_count": 0,
    "cost_usd": 0.35,
    "tokens_used": 2140,
    "queued_at": "2025-12-05T15:00:00Z",
    "started_at": "2025-12-05T15:00:05Z",
    "completed_at": "2025-12-05T15:00:28Z",
    "duration_seconds": 23,
    "created_at": "2025-12-05T15:00:00Z",
    "updated_at": "2025-12-05T15:00:28Z"
  },
  "meta": {
    "request_id": "req_job001"
  }
}
```

**Response (In Progress):** `200 OK`

```json
{
  "data": {
    "id": "job_bb0e8400-e29b-41d4-a716-446655440006",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "episode": {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "title": "What Happens Inside a Black Hole?",
      "channel_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "stage": "scripting",
    "status": "processing",
    "progress": {
      "percent": 45,
      "current_step": "generating_segments",
      "steps_completed": 2,
      "steps_total": 5,
      "message": "Generating script segments (section 2 of 4)..."
    },
    "worker_id": "worker-02",
    "params": {
      "model": "gpt-4.1",
      "temperature": 0.8,
      "include_qa_pass": true
    },
    "result": null,
    "error_message": null,
    "retry_count": 0,
    "cost_usd": null,
    "tokens_used": null,
    "queued_at": "2025-12-05T15:05:00Z",
    "started_at": "2025-12-05T15:05:10Z",
    "completed_at": null,
    "duration_seconds": null,
    "created_at": "2025-12-05T15:05:00Z",
    "updated_at": "2025-12-05T15:06:30Z"
  },
  "meta": {
    "request_id": "req_job002",
    "poll_interval_seconds": 5
  }
}
```

**Response (Failed):** `200 OK`

```json
{
  "data": {
    "id": "job_cc0e8400-e29b-41d4-a716-446655440007",
    "episode_id": "880e8400-e29b-41d4-a716-446655440003",
    "episode": {
      "id": "880e8400-e29b-41d4-a716-446655440003",
      "title": "What Happens Inside a Black Hole?",
      "channel_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "stage": "audio",
    "status": "failed",
    "progress": null,
    "worker_id": "worker-03",
    "params": {
      "provider": "elevenlabs",
      "voice_id": "pNInz6obpgDQGcFmaJgB"
    },
    "result": null,
    "error_message": "ElevenLabs API error: Rate limit exceeded. Please retry after 60 seconds.",
    "retry_count": 2,
    "cost_usd": 0.12,
    "tokens_used": null,
    "queued_at": "2025-12-05T15:30:00Z",
    "started_at": "2025-12-05T15:30:05Z",
    "completed_at": "2025-12-05T15:31:15Z",
    "duration_seconds": 70,
    "created_at": "2025-12-05T15:30:00Z",
    "updated_at": "2025-12-05T15:31:15Z"
  },
  "meta": {
    "request_id": "req_job003",
    "retry_eligible": true,
    "next_retry_after": "2025-12-05T15:32:15Z"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized |
| 404 | Job not found |
| 500 | Internal server error |

---

### 8.2 List Episode Jobs

Retrieves a list of jobs for an episode, optionally filtered by stage or status.

**Endpoint:** `GET /api/v1/episodes/{episode_id}/jobs`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| episode_id | uuid | Yes | Episode unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| page | integer | No | 1 | Page number (1-indexed) |
| page_size | integer | No | 20 | Items per page (max 100) |
| stage | string | No | - | Filter by stage (comma-separated for multiple) |
| status | string | No | - | Filter by status (comma-separated for multiple) |
| sort_by | string | No | created_at | Sort field: `created_at`, `stage`, `status` |
| sort_order | string | No | desc | Sort order: `asc` or `desc` |

**Example Request:**

```
GET /api/v1/episodes/880e8400-e29b-41d4-a716-446655440003/jobs?status=completed,failed&sort_by=created_at&sort_order=desc
```

**Response:** `200 OK`

```json
{
  "data": [
    {
      "id": "job_aa0e8400-e29b-41d4-a716-446655440005",
      "episode_id": "880e8400-e29b-41d4-a716-446655440003",
      "stage": "planning",
      "status": "completed",
      "worker_id": "worker-01",
      "retry_count": 0,
      "cost_usd": 0.35,
      "queued_at": "2025-12-05T15:00:00Z",
      "started_at": "2025-12-05T15:00:05Z",
      "completed_at": "2025-12-05T15:00:28Z",
      "duration_seconds": 23
    },
    {
      "id": "job_bb0e8400-e29b-41d4-a716-446655440006",
      "episode_id": "880e8400-e29b-41d4-a716-446655440003",
      "stage": "scripting",
      "status": "completed",
      "worker_id": "worker-02",
      "retry_count": 0,
      "cost_usd": 0.50,
      "queued_at": "2025-12-05T15:05:00Z",
      "started_at": "2025-12-05T15:05:10Z",
      "completed_at": "2025-12-05T15:06:45Z",
      "duration_seconds": 95
    }
  ],
  "meta": {
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 2,
      "total_pages": 1,
      "has_next": false,
      "has_prev": false
    },
    "filters_applied": {
      "status": ["completed", "failed"]
    },
    "request_id": "req_job004"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Invalid query parameters |
| 401 | Unauthorized |
| 404 | Episode not found |
| 500 | Internal server error |

---

### 8.3 Cancel Job

Cancels a queued or in-progress job.

**Endpoint:** `POST /api/v1/jobs/{job_id}/cancel`

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | uuid | Yes | Job unique identifier |

**Request Body:**

```yaml
CancelJobRequest:
  type: object
  properties:
    reason:
      type: string
      maxLength: 500
      description: Reason for cancellation
```

**Example Request:**

```json
{
  "reason": "User requested cancellation"
}
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "job_bb0e8400-e29b-41d4-a716-446655440006",
    "stage": "scripting",
    "previous_status": "processing",
    "status": "cancelled",
    "cancelled_at": "2025-12-05T15:10:00Z",
    "reason": "User requested cancellation"
  },
  "meta": {
    "request_id": "req_job005"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Job cancelled successfully |
| 401 | Unauthorized |
| 404 | Job not found |
| 409 | Conflict (job already completed, failed, or cancelled) |
| 500 | Internal server error |

---

## 9. Authentication Endpoints

### 9.1 Login

Authenticates a user and returns access and refresh tokens.

**Endpoint:** `POST /api/v1/auth/login`

**Authentication:** None required

**Request Body:**

```yaml
LoginRequest:
  type: object
  required:
    - email
    - password
  properties:
    email:
      type: string
      format: email
      description: User email address
      example: "user@example.com"
    password:
      type: string
      format: password
      minLength: 8
      description: User password
      example: "securePassword123"
```

**Example Request:**

```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response:** `200 OK`

```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoidXNlckBleGFtcGxlLmNvbSIsInJvbGUiOiJlZGl0b3IiLCJwZXJtaXNzaW9ucyI6WyJjaGFubmVsczpyZWFkIiwiY2hhbm5lbHM6d3JpdGUiXSwiaWF0IjoxNzMzNDA3ODAwLCJleHAiOjE3MzM0MDg3MDAsImlzcyI6ImFjb2ctYXBpIn0.signature",
    "refresh_token": "rt_abc123def456ghi789jkl012mno345pqr678stu901",
    "token_type": "Bearer",
    "expires_in": 900,
    "expires_at": "2025-12-05T15:15:00Z",
    "refresh_expires_in": 604800,
    "refresh_expires_at": "2025-12-12T15:00:00Z",
    "user": {
      "id": "user_123",
      "email": "user@example.com",
      "name": "John Doe",
      "role": "editor",
      "permissions": [
        "channels:read",
        "channels:write",
        "episodes:read",
        "episodes:write",
        "pipeline:execute"
      ],
      "created_at": "2025-01-15T10:00:00Z",
      "last_login_at": "2025-12-05T15:00:00Z"
    }
  },
  "meta": {
    "request_id": "req_auth001"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Login successful |
| 400 | Invalid request body |
| 401 | Invalid credentials |
| 403 | Account disabled or locked |
| 429 | Too many login attempts |
| 500 | Internal server error |

---

### 9.2 Logout

Invalidates the current access and refresh tokens.

**Endpoint:** `POST /api/v1/auth/logout`

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Request Body:**

```yaml
LogoutRequest:
  type: object
  properties:
    refresh_token:
      type: string
      description: Refresh token to invalidate (optional, invalidates all if not provided)
      example: "rt_abc123def456ghi789jkl012mno345pqr678stu901"
    all_sessions:
      type: boolean
      default: false
      description: Invalidate all sessions for this user
```

**Example Request:**

```json
{
  "refresh_token": "rt_abc123def456ghi789jkl012mno345pqr678stu901",
  "all_sessions": false
}
```

**Response:** `200 OK`

```json
{
  "data": {
    "logged_out": true,
    "sessions_invalidated": 1
  },
  "meta": {
    "request_id": "req_auth002"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Logout successful |
| 401 | Unauthorized (token already invalid) |
| 500 | Internal server error |

---

### 9.3 Refresh Token

Obtains a new access token using a valid refresh token.

**Endpoint:** `POST /api/v1/auth/refresh`

**Authentication:** None required (refresh token in body)

**Request Body:**

```yaml
RefreshTokenRequest:
  type: object
  required:
    - refresh_token
  properties:
    refresh_token:
      type: string
      description: Valid refresh token
      example: "rt_abc123def456ghi789jkl012mno345pqr678stu901"
```

**Example Request:**

```json
{
  "refresh_token": "rt_abc123def456ghi789jkl012mno345pqr678stu901"
}
```

**Response:** `200 OK`

```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.newtoken...",
    "refresh_token": "rt_new123def456ghi789jkl012mno345pqr678stu901",
    "token_type": "Bearer",
    "expires_in": 900,
    "expires_at": "2025-12-05T15:30:00Z",
    "refresh_expires_in": 604800,
    "refresh_expires_at": "2025-12-12T15:15:00Z"
  },
  "meta": {
    "request_id": "req_auth003",
    "token_rotated": true
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Token refreshed successfully |
| 400 | Invalid request body |
| 401 | Invalid or expired refresh token |
| 403 | Refresh token revoked |
| 500 | Internal server error |

---

### 9.4 Get Current User

Retrieves information about the currently authenticated user.

**Endpoint:** `GET /api/v1/auth/me`

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Example Request:**

```
GET /api/v1/auth/me
```

**Response:** `200 OK`

```json
{
  "data": {
    "id": "user_123",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "editor",
    "permissions": [
      "channels:read",
      "channels:write",
      "episodes:read",
      "episodes:write",
      "pipeline:execute",
      "assets:read",
      "assets:write"
    ],
    "preferences": {
      "theme": "dark",
      "notifications_enabled": true,
      "default_channel_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "api_keys": [
      {
        "id": "key_001",
        "name": "CLI Access",
        "prefix": "acog_abc1",
        "last_used_at": "2025-12-05T14:00:00Z",
        "created_at": "2025-11-01T10:00:00Z"
      }
    ],
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-12-05T15:00:00Z",
    "last_login_at": "2025-12-05T15:00:00Z"
  },
  "meta": {
    "request_id": "req_auth004"
  }
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Unauthorized (invalid or expired token) |
| 500 | Internal server error |

---

### 9.5 JWT Token Structure

Access tokens are JWTs with the following structure:

**Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "sub": "user_123",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "editor",
  "permissions": [
    "channels:read",
    "channels:write",
    "episodes:read",
    "episodes:write",
    "pipeline:execute"
  ],
  "iat": 1733407800,
  "exp": 1733408700,
  "iss": "acog-api",
  "aud": "acog-clients",
  "jti": "token_unique_id_123"
}
```

**Token Expiration:**

| Token Type | Default Expiration | Max Expiration |
|------------|-------------------|----------------|
| Access Token | 15 minutes | 1 hour |
| Refresh Token | 7 days | 30 days |
| API Key | No expiration | No expiration |

**Refresh Flow:**

1. Client uses access token for API requests
2. When access token expires (or ~1 minute before), client calls `/auth/refresh`
3. Server validates refresh token and issues new access + refresh tokens
4. Old refresh token is invalidated (rotation)
5. Client stores new tokens and continues

---

## 10. System Endpoints

### 10.1 Health Check (Liveness)

Basic health check to verify the API server is running.

**Endpoint:** `GET /api/v1/health`

**Authentication:** None required

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "timestamp": "2025-12-05T14:30:00Z",
  "version": "1.0.0",
  "environment": "production"
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | Server is healthy |
| 500 | Server is unhealthy |

---

### 10.2 Readiness Check

Comprehensive readiness check verifying all dependencies are connected.

**Endpoint:** `GET /api/v1/health/ready`

**Authentication:** None required (or internal only)

**Response:** `200 OK`

```json
{
  "status": "ready",
  "timestamp": "2025-12-05T14:30:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2,
      "details": {
        "pool_size": 10,
        "active_connections": 3
      }
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1,
      "details": {
        "connected_clients": 5,
        "used_memory_mb": 128
      }
    },
    "celery": {
      "status": "healthy",
      "active_workers": 4,
      "queued_tasks": 12
    },
    "storage": {
      "status": "healthy",
      "provider": "s3",
      "latency_ms": 45
    },
    "openai": {
      "status": "healthy",
      "latency_ms": 150,
      "rate_limit_remaining": 9500
    }
  },
  "version": "1.0.0"
}
```

**Response (Degraded):** `200 OK` (still operational but with issues)

```json
{
  "status": "degraded",
  "timestamp": "2025-12-05T14:30:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1
    },
    "celery": {
      "status": "degraded",
      "active_workers": 1,
      "queued_tasks": 150,
      "warning": "High queue depth, processing may be delayed"
    },
    "storage": {
      "status": "healthy",
      "provider": "s3",
      "latency_ms": 45
    },
    "openai": {
      "status": "degraded",
      "latency_ms": 2500,
      "warning": "High latency detected"
    }
  },
  "version": "1.0.0"
}
```

**Response (Not Ready):** `503 Service Unavailable`

```json
{
  "status": "not_ready",
  "timestamp": "2025-12-05T14:30:00Z",
  "checks": {
    "database": {
      "status": "unhealthy",
      "error": "Connection refused"
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1
    },
    "celery": {
      "status": "unhealthy",
      "active_workers": 0,
      "error": "No workers available"
    },
    "storage": {
      "status": "healthy",
      "provider": "s3"
    },
    "openai": {
      "status": "unknown",
      "error": "Check skipped due to database failure"
    }
  },
  "version": "1.0.0"
}
```

**Status Codes:**

| Code | Description |
|------|-------------|
| 200 | System ready (or degraded but operational) |
| 503 | System not ready (critical dependency down) |

---

## 11. Error Handling

### 11.1 Standard Error Response Format

All errors follow this consistent structure:

```yaml
ErrorResponse:
  type: object
  required:
    - error
  properties:
    error:
      type: object
      required:
        - code
        - message
      properties:
        code:
          type: string
          description: Machine-readable error code
          example: "VALIDATION_ERROR"
        message:
          type: string
          description: Human-readable error message
          example: "The request body contains invalid fields"
        details:
          type: object
          description: Additional error context
          additionalProperties: true
        field_errors:
          type: array
          description: Field-specific validation errors
          items:
            type: object
            properties:
              field:
                type: string
                example: "persona.name"
              message:
                type: string
                example: "Field is required"
              code:
                type: string
                example: "required"
        request_id:
          type: string
          description: Request ID for debugging
          example: "req_abc123"
        timestamp:
          type: string
          format: date-time
          example: "2025-12-05T14:30:00Z"
```

### 11.2 Error Codes Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request body failed validation |
| `INVALID_PARAMETER` | 400 | Query or path parameter invalid |
| `MALFORMED_JSON` | 400 | Request body is not valid JSON |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Authenticated but not authorized |
| `NOT_FOUND` | 404 | Resource does not exist |
| `METHOD_NOT_ALLOWED` | 405 | HTTP method not supported |
| `CONFLICT` | 409 | Resource state conflict |
| `UNPROCESSABLE_ENTITY` | 422 | Semantic validation error |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SERVICE_UNAVAILABLE` | 503 | Dependency unavailable |
| `GATEWAY_TIMEOUT` | 504 | Upstream service timeout |

### 11.3 Error Examples

**Validation Error (400):**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request body contains invalid fields",
    "field_errors": [
      {
        "field": "persona.name",
        "message": "Field is required",
        "code": "required"
      },
      {
        "field": "style_guide.tone",
        "message": "Must be one of: formal, conversational, casual, academic, enthusiastic",
        "code": "invalid_enum"
      }
    ],
    "request_id": "req_abc123",
    "timestamp": "2025-12-05T14:30:00Z"
  }
}
```

**Resource Not Found (404):**

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Channel not found",
    "details": {
      "resource_type": "channel",
      "resource_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "request_id": "req_def456",
    "timestamp": "2025-12-05T14:30:00Z"
  }
}
```

**Conflict (409):**

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Cannot delete channel with in-progress episodes",
    "details": {
      "in_progress_episodes": 3,
      "episode_ids": [
        "880e8400-e29b-41d4-a716-446655440003",
        "880e8400-e29b-41d4-a716-446655440004",
        "880e8400-e29b-41d4-a716-446655440005"
      ],
      "suggestion": "Use cascade_episodes=true to delete episodes, or cancel their pipelines first"
    },
    "request_id": "req_ghi789",
    "timestamp": "2025-12-05T14:30:00Z"
  }
}
```

**Rate Limited (429):**

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please slow down.",
    "details": {
      "limit": 100,
      "window_seconds": 60,
      "retry_after_seconds": 23
    },
    "request_id": "req_jkl012",
    "timestamp": "2025-12-05T14:30:00Z"
  }
}
```

**Service Unavailable (503):**

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "OpenAI API is currently unavailable",
    "details": {
      "service": "openai",
      "last_error": "Connection timeout",
      "retry_after_seconds": 30
    },
    "request_id": "req_mno345",
    "timestamp": "2025-12-05T14:30:00Z"
  }
}
```

---

## 12. Pagination

### 12.1 Request Parameters

All list endpoints support these pagination parameters:

| Parameter | Type | Default | Max | Description |
|-----------|------|---------|-----|-------------|
| page | integer | 1 | - | Page number (1-indexed) |
| page_size | integer | 20 | 100 | Items per page |

### 12.2 Response Metadata

```json
{
  "data": [...],
  "meta": {
    "pagination": {
      "page": 2,
      "page_size": 20,
      "total_items": 157,
      "total_pages": 8,
      "has_next": true,
      "has_prev": true
    }
  }
}
```

### 12.3 Link Headers (Optional)

For clients that prefer Link headers:

```
Link: </api/v1/channels?page=1&page_size=20>; rel="first",
      </api/v1/channels?page=3&page_size=20>; rel="next",
      </api/v1/channels?page=1&page_size=20>; rel="prev",
      </api/v1/channels?page=8&page_size=20>; rel="last"
```

---

## 13. Authentication

### 13.1 Bearer Token Authentication

All endpoints (except health checks) require authentication via Bearer token:

```
Authorization: Bearer <access_token>
```

### 13.2 Token Types

**Access Token:**
- Short-lived (15 minutes default)
- Used for API requests
- JWT format with claims

**Refresh Token:**
- Long-lived (7 days default)
- Used to obtain new access tokens
- Stored securely, rotated on use

**API Key (CLI):**
- Long-lived personal access token
- Used for CLI and automation
- Prefixed with `acog_` for identification

### 13.3 Token Claims (JWT)

```json
{
  "sub": "user_123",
  "email": "user@example.com",
  "role": "editor",
  "permissions": ["channels:read", "channels:write", "episodes:read", "episodes:write", "pipeline:execute"],
  "iat": 1733407800,
  "exp": 1733408700,
  "iss": "acog-api"
}
```

### 13.4 Roles and Permissions

| Role | Permissions |
|------|-------------|
| viewer | Read-only access to channels and episodes |
| editor | Full CRUD on channels and episodes, execute pipelines |
| admin | All permissions including user management |

---

## 14. Rate Limiting

### 14.1 Rate Limit Headers

All responses include rate limit headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1733408700
```

### 14.2 Rate Limits by Endpoint Type

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Read (GET) | 1000 | 1 minute |
| Write (POST/PUT/DELETE) | 100 | 1 minute |
| Pipeline triggers | 20 | 1 minute |
| Health checks | Unlimited | - |

### 14.3 Rate Limit Response

When rate limited, the API returns `429 Too Many Requests` with a `Retry-After` header:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 23
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1733408700
```

---

## 15. Versioning Strategy

### 15.1 URL-Based Versioning

API version is included in the URL path:

```
/api/v1/channels
/api/v2/channels  (future)
```

### 15.2 Version Lifecycle

| Version | Status | Support Until |
|---------|--------|---------------|
| v1 | Current | - |

### 15.3 Deprecation Policy

1. New versions announced 3 months before release
2. Old versions supported for 6 months after new version release
3. Deprecation warnings via `X-API-Deprecated` header
4. Migration guides provided for breaking changes

### 15.4 Backward Compatibility

Within a version, we maintain backward compatibility:
- New fields may be added to responses
- New optional parameters may be added to requests
- Existing fields and parameters will not be removed or renamed
- Enum values will not be removed (may be deprecated)

---

## Appendix A: OpenAPI 3.0 Specification

The complete OpenAPI 3.0 specification is available at:

```
GET /api/v1/openapi.json
GET /api/v1/docs  (Swagger UI)
GET /api/v1/redoc (ReDoc)
```

---

## Appendix B: CLI Usage Examples

### Create a Channel

```bash
acog channel create \
  --name "Cosmic Horizons" \
  --niche "cosmology" \
  --persona-file persona.json \
  --style-guide-file style.json
```

### Create an Episode

```bash
acog episode create \
  --channel "Cosmic Horizons" \
  --title "What Happens Inside a Black Hole?" \
  --brief "Explore the theoretical physics of black hole interiors" \
  --tags "black holes,physics,space"
```

### Trigger Planning

```bash
acog pipeline plan \
  --episode-id 880e8400-e29b-41d4-a716-446655440003 \
  --model gpt-4.1 \
  --wait
```

### Check Pipeline Status

```bash
acog pipeline status --episode-id 880e8400-e29b-41d4-a716-446655440003
```

### Retry Failed Stage

```bash
acog pipeline retry \
  --episode-id 880e8400-e29b-41d4-a716-446655440003 \
  --stage scripting \
  --reset-downstream
```

---

## Appendix C: Dashboard Integration Notes

### Real-Time Updates

The dashboard should poll `/api/v1/episodes/{id}/pipeline/status` every 5 seconds when viewing an episode with an active pipeline. Future versions will support WebSocket subscriptions for real-time updates.

### Optimistic Updates

For better UX, the dashboard can implement optimistic updates:
1. Update local state immediately on user action
2. Send API request in background
3. Reconcile on response or rollback on error

### Error Display

Map error codes to user-friendly messages:
- `CONFLICT` -> "This action cannot be completed right now. [Details]"
- `VALIDATION_ERROR` -> Show field-specific errors inline
- `SERVICE_UNAVAILABLE` -> "Service temporarily unavailable. Retrying..."

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-05 | ACOG Architecture Team | Initial API contracts for Phase 1 |
| 1.1.0 | 2025-12-05 | ACOG Architecture Team | Added Asset endpoints (6.1-6.4), Job endpoints (8.1-8.3), Authentication endpoints (9.1-9.5). Standardized pipeline stage names across all documentation. |
