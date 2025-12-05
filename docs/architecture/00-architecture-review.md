# ACOG Phase 1 Architecture Review

**Document ID:** ARCH-REVIEW-001
**Version:** 1.0
**Review Date:** 2025-12-05
**Reviewer:** Lead Reviewer / QA Engineer
**Status:** Complete

---

## Executive Summary

The three Phase 1 architecture documents (Repository Structure, Database Schema, API Contracts) represent **solid foundational work** that demonstrates thoughtful design and attention to enterprise patterns. The documents are well-organized, comprehensive, and largely aligned with the ACOG Foundational Proposal. However, there are **several critical consistency issues** between documents, **missing MVP elements**, and **security gaps** that must be addressed before implementation begins.

**Overall Assessment:** The architecture is 85% implementation-ready. With the corrections outlined below, the team can proceed to parallel backend/frontend development with confidence.

---

## Document 1: Repository Structure (01-repository-structure.md)

### Summary

Excellent monorepo structure with clear separation of concerns. The document provides comprehensive coverage of folder organization, Docker configuration, CI/CD pipelines, and development workflows.

### Critical Issues

**[CRIT-RS-1] Missing Users Table Implementation Path**

The repository structure includes `models/user.py` in the backend module organization, but the database schema document (02-database-schema.md) lists the Users table as "Post-MVP" (Future Extensions). This creates confusion about Phase 1 authentication scope.

- **Location:** `apps/api/src/acog/models/user.py` (line 137)
- **Impact:** Blocks authentication implementation
- **Fix:** Either add Users table to Phase 1 schema OR remove user.py from Phase 1 structure and clarify auth will use simplified/mock auth for MVP

**[CRIT-RS-2] Inconsistent Alembic Directory Location**

- Repository Structure shows: `apps/api/alembic/` (line 89-92)
- Database Schema shows: `backend/alembic/` (line 515-524)

The "backend" naming doesn't match the `apps/api/` convention established in the repository structure.

- **Fix:** Database schema should reference `apps/api/alembic/` to maintain consistency

### Significant Findings

**[HIGH-RS-1] Missing Job/Task Model in Repository Structure**

The foundational proposal specifies "job handling" as a Phase 1 deliverable. The repository structure includes:
- `apps/api/src/acog/models/job.py` (line 135)
- `apps/api/src/acog/api/v1/jobs.py` (line 108)

However, the database schema document has NO `jobs` table defined. The API contracts reference job IDs extensively (e.g., `job_aa0e8400-e29b-41d4-a716-446655440005`).

- **Impact:** Backend cannot implement job status tracking without schema definition
- **Fix:** Add `jobs` table to database schema document (see Recommended Actions section)

**[HIGH-RS-2] Webhook Endpoints Not in API Contracts**

Repository structure includes `apps/api/src/acog/api/webhooks/` with:
- `heygen.py` - HeyGen completion callbacks
- `pulse.py` - Pulse event intake

Neither webhook endpoint is documented in the API contracts document.

- **Impact:** Frontend/integration teams have no contract for these endpoints
- **Fix:** Add webhook endpoint documentation to API contracts OR mark as Phase 2

**[MED-RS-3] Docker Compose Version Deprecated**

```yaml
version: "3.8"  # Line 373
```

The `version` key is deprecated in modern Docker Compose (v2.0+). While harmless, it will generate warnings.

- **Fix:** Remove the `version:` line entirely

**[MED-RS-4] Missing Test for OpenAI Mock in CI**

The CI pipeline sets `OPENAI_API_KEY: sk-test-key` (line 1097), but there's no documented mock/stub strategy for OpenAI integration tests. Tests hitting actual OpenAI would fail with this key.

- **Fix:** Document mocking strategy for external services in test suite

### Positive Observations

1. **Excellent Docker configuration** - Multi-stage builds, health checks, non-root users, proper volume mounts
2. **Comprehensive CI/CD pipeline** - Path-based filtering, parallel jobs, caching strategy
3. **Strong Python project configuration** - Ruff, mypy strict mode, proper pytest setup
4. **Well-designed Makefile** - Clear targets, good developer experience
5. **Future-proof structure** - Clear path for Phase 2+ extensions (k8s, terraform, monitoring)
6. **Consistent naming conventions table** - Excellent reference for team alignment

### Scoring Matrix

| Dimension | Score | Justification |
|-----------|-------|---------------|
| **Quality** | 8/10 | Comprehensive coverage with minor gaps in job tracking and webhooks |
| **Clarity** | 9/10 | Excellent documentation, clear examples, well-organized |
| **Maintainability** | 9/10 | Modular design, clear separation, standard tooling |
| **Future Reliability** | 8/10 | Good Phase 2+ extension paths documented |
| **Consistency with Roadmap** | 7/10 | Missing user model clarity, job table gap with other docs |

---

## Document 2: Database Schema (02-database-schema.md)

### Summary

Well-designed PostgreSQL schema with proper use of UUIDs, soft deletes, JSONB for flexibility, and strategic indexing. The SQLAlchemy models are clean and follow best practices.

### Critical Issues

**[CRIT-DB-1] Missing Jobs/Tasks Table**

The API contracts document references job IDs extensively:
- `job_aa0e8400-e29b-41d4-a716-446655440005` (API contracts line 1683)
- `POST /api/v1/episodes/{id}/pipeline/plan` returns `job_id` (line 1682)
- Pipeline status shows `active_jobs` array (line 1952)

There is NO jobs table in the database schema. This is a blocking gap.

- **Impact:** Cannot implement async job tracking for pipeline operations
- **Required Fix:** Add jobs table (proposed schema below)

**[CRIT-DB-2] Episode Status Enum Mismatch**

Database Schema defines `episode_status` as:
```sql
'idea', 'planning', 'scripting', 'production', 'review', 'publishing', 'published', 'failed', 'cancelled'
```

API Contracts define `EpisodeStatus` as:
```yaml
'idea', 'planning', 'scripting', 'script_review', 'production', 'assembly', 'ready', 'publishing', 'published', 'failed', 'cancelled'
```

**Differences:**
- DB has `review` | API has `script_review`
- DB missing `assembly` | API has it
- DB missing `ready` | API has it

- **Impact:** Frontend and backend will have status value mismatches
- **Fix:** Align enum values across both documents (recommend adopting API version as more granular)

**[CRIT-DB-3] Pipeline Stage Names Mismatch**

Database `pipeline_state` JSON example (line 396-439) uses:
```
planning, scripting, audio_generation, avatar_video, b_roll, assembly, upload
```

API contracts `PipelineState` schema (line 343-344) uses:
```
idea, planning, scripting, script_review, metadata, audio, avatar, broll, assembly, upload, published
```

**Key differences:**
- DB: `audio_generation` | API: `audio`
- DB: `avatar_video` | API: `avatar`
- DB: `b_roll` | API: `broll`
- API has `metadata` stage, DB doesn't
- API has `script_review` stage, DB has it as status only

- **Impact:** Pipeline state parsing will fail between frontend and backend
- **Fix:** Standardize stage names across all documents

### Significant Findings

**[HIGH-DB-1] Missing slug Uniqueness Constraint per Channel**

Episodes table has `slug VARCHAR(200)` but no uniqueness constraint. The API contracts imply slugs should be unique within a channel (e.g., for URL routing `/channels/{slug}/episodes/{slug}`).

- **Fix:** Add `CREATE UNIQUE INDEX idx_episodes_slug_per_channel ON episodes(channel_id, slug) WHERE deleted_at IS NULL;`

**[HIGH-DB-2] Asset Provider Enum Not Defined**

Assets table has `provider VARCHAR(100)` but the API contracts define strict provider enums:
- VoiceProfile: `elevenlabs, amazon_polly, google_tts`
- AvatarProfile: `heygen, synthesia, d-id`

Consider adding a provider enum or validation to ensure data consistency.

**[MED-DB-3] Channel Missing niche Column**

API contracts include `niche` field in channel responses (line 664: `"niche": "cosmology"`), but the database schema has no `niche` column in the channels table.

- **Fix:** Add `niche VARCHAR(100)` to channels table

**[MED-DB-4] Episode Missing cost_tracking Column**

API contracts show `cost_tracking` object in episode responses (lines 1125-1128, 1416-1422), but the database schema has no cost tracking columns on the episode table. The cost_entries table is listed as "Phase 2+".

- **Options:**
  1. Add inline cost tracking to episodes table (simple, MVP-friendly)
  2. Remove cost_tracking from API contracts until Phase 2
  3. Move cost_entries table to Phase 1

**[MED-DB-5] Updated_at Trigger Not Implemented**

The schema mentions `onupdate=func.now()` in SQLAlchemy models (line 724), but no PostgreSQL trigger is defined to automatically update `updated_at`. SQLAlchemy's `onupdate` only works within SQLAlchemy sessions, not direct SQL updates.

- **Fix:** Add trigger for consistency:
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_channels_updated_at BEFORE UPDATE ON channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
-- Repeat for episodes, assets, etc.
```

**[LOW-DB-1] Missing Database Collation Specification**

No collation specified for text columns. For internationalization readiness, consider specifying collation:
```sql
name VARCHAR(255) COLLATE "en_US.UTF-8" NOT NULL
```

### Positive Observations

1. **Excellent soft delete pattern** - Consistent `deleted_at` across all tables with partial indexes
2. **Strategic use of JSONB** - Persona, style_guide, pipeline_state properly use JSONB for flexibility
3. **Comprehensive indexing** - Good coverage of query patterns, proper partial indexes
4. **Well-documented JSON schemas** - Clear examples for all JSONB fields
5. **Clean SQLAlchemy models** - Type hints, proper relationships, useful helper methods
6. **Good FK constraints** - RESTRICT on channel->episode, CASCADE on episode->asset
7. **Decision log** - Excellent documentation of architectural decisions with reasoning

### Scoring Matrix

| Dimension | Score | Justification |
|-----------|-------|---------------|
| **Quality** | 7/10 | Strong foundation but missing jobs table is critical |
| **Clarity** | 9/10 | Excellent documentation, clear JSON examples |
| **Maintainability** | 8/10 | Good migration strategy, but enum sync issues |
| **Future Reliability** | 8/10 | Clear Phase 2+ extensions, soft deletes |
| **Consistency with Roadmap** | 6/10 | Major gaps with API contracts (status, stages, jobs) |

---

## Document 3: API Contracts (03-api-contracts.md)

### Summary

Comprehensive REST API specification with excellent detail on request/response schemas, error handling, pagination, and authentication. The document provides clear contracts for frontend and CLI development.

### Critical Issues

**[CRIT-API-1] Asset Endpoints Missing**

The foundational proposal specifies "Asset retrieval endpoints" as Phase 1 deliverable. The repository structure includes `apps/api/src/acog/api/v1/assets.py` (line 107). However, the API contracts document has NO asset endpoints defined.

Missing endpoints needed for MVP:
- `GET /api/v1/episodes/{episode_id}/assets` - List assets for episode
- `GET /api/v1/assets/{asset_id}` - Get single asset details
- `GET /api/v1/assets/{asset_id}/download` - Get presigned download URL

- **Impact:** Frontend cannot display or download generated assets
- **Fix:** Add Asset endpoints section to API contracts

**[CRIT-API-2] Authentication Endpoints Missing**

The document references Bearer token authentication but provides no auth endpoints:
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - Logout
- `GET /api/v1/auth/me` - Get current user

The repository structure includes `apps/api/src/acog/api/v1/auth.py` (line 109).

- **Impact:** Frontend cannot implement authentication flow
- **Fix:** Add Authentication section with endpoint specifications

**[CRIT-API-3] Episode Endpoint Inconsistency**

Episode creation uses nested route:
```
POST /api/v1/channels/{channel_id}/episodes  (line 961)
```

But episode detail/update/delete uses flat route:
```
GET /api/v1/episodes/{episode_id}  (line 1256)
PUT /api/v1/episodes/{episode_id}  (line 1467)
DELETE /api/v1/episodes/{episode_id}  (line 1574)
```

While this can work, it's inconsistent and may confuse API consumers.

- **Recommendation:** Document the rationale OR standardize on one approach
- **Preferred:** Keep current design but add explicit note explaining the pattern (create under channel, operate directly on episode)

### Significant Findings

**[HIGH-API-1] Pipeline Stages Incomplete**

API defines 11 pipeline stages (line 343-344):
```
idea, planning, scripting, script_review, metadata, audio, avatar, broll, assembly, upload, published
```

But only documents trigger endpoints for:
- Planning (`POST /api/v1/episodes/{id}/pipeline/plan`)
- Scripting (`POST /api/v1/episodes/{id}/pipeline/script`)

Missing for Phase 1 (per foundational proposal):
- `POST /api/v1/episodes/{id}/pipeline/metadata` - Trigger metadata generation
- Endpoints for media stages (audio, avatar, broll) are Phase 2, acceptable to defer

**[HIGH-API-2] WebSocket/SSE for Real-Time Updates**

The document mentions (line 2709):
> "Future versions will support WebSocket subscriptions for real-time updates."

But the foundational proposal (line 149) specifies:
> "Communicates with backend via REST + WebSocket"

WebSocket support should be documented as Phase 1 requirement for pipeline status updates.

- **Fix:** Add WebSocket endpoint specification or explicitly defer to Phase 2 with polling fallback

**[HIGH-API-3] Pulse Event Endpoints Missing**

The repository structure includes `apps/api/src/acog/api/webhooks/pulse.py`. The database schema includes `pulse_events` table. But API contracts has no Pulse endpoints.

Needed endpoints:
- `POST /api/v1/pulse/events` - Receive pulse event (webhook)
- `GET /api/v1/pulse/events` - List pulse events
- `GET /api/v1/pulse/events/{id}` - Get pulse event details

**[MED-API-1] Priority Enum Mismatch**

Episode create request uses string enum for priority (line 1017-1022):
```yaml
priority:
  type: string
  enum: [low, normal, high, urgent]
```

Database schema uses integer priority (line 176):
```sql
priority INTEGER NOT NULL DEFAULT 0
```

- **Impact:** Backend must translate string to integer
- **Fix:** Either use integer in API OR use enum in database. Recommend keeping string in API for readability with backend translation.

**[MED-API-2] Missing Idempotency Key Storage**

Document specifies (line 86-88):
> "All POST endpoints accept an optional `X-Idempotency-Key` header"
> "Keys expire after 24 hours"

But there's no database table or Redis key schema for storing idempotency keys.

- **Fix:** Add idempotency implementation note to database schema or core infrastructure docs

**[LOW-API-1] Missing CORS Configuration**

No CORS policy documented. Frontend running on different origin (localhost:3000 vs localhost:8000) needs CORS.

- **Fix:** Add CORS configuration section specifying allowed origins, methods, headers

**[LOW-API-2] OpenAPI Spec Reference**

Document references (lines 2650-2653):
```
GET /api/v1/openapi.json
GET /api/v1/docs  (Swagger UI)
GET /api/v1/redoc (ReDoc)
```

These should be added to System Endpoints section formally.

### Positive Observations

1. **Comprehensive request/response schemas** - All fields documented with types, constraints, examples
2. **Excellent error handling specification** - Standard error format, complete error codes reference
3. **Well-designed pagination** - Offset-based with proper metadata and optional Link headers
4. **Rate limiting documented** - Clear limits by endpoint type with proper headers
5. **Authentication roles defined** - Clear permission model (viewer, editor, admin)
6. **Detailed pipeline state tracking** - Granular stage status with progress indicators
7. **CLI examples** - Helpful for CLI developer understanding API usage patterns
8. **Dashboard integration notes** - Useful guidance for frontend implementation

### Scoring Matrix

| Dimension | Score | Justification |
|-----------|-------|---------------|
| **Quality** | 7/10 | Comprehensive but missing critical endpoints (assets, auth) |
| **Clarity** | 9/10 | Excellent detail, clear examples, well-organized |
| **Maintainability** | 8/10 | Good versioning strategy, backward compatibility policy |
| **Future Reliability** | 8/10 | Solid foundation, clear extension points |
| **Consistency with Roadmap** | 7/10 | Missing several Phase 1 requirements |

---

## Cross-Document Consistency Analysis

### Entity/Field Mapping Issues

| Entity | Issue | Documents Affected |
|--------|-------|-------------------|
| Episode Status | 9 values in DB, 11 in API | DB, API |
| Pipeline Stages | Different naming conventions | DB, API |
| Jobs Table | Missing from schema | All three |
| Asset Endpoints | Defined in structure, missing from API | Repo, API |
| Auth Endpoints | Defined in structure, missing from API | Repo, API |
| Channel.niche | In API response, not in DB schema | DB, API |
| Episode.cost_tracking | In API response, not in DB schema | DB, API |
| Users Table | In repo structure, deferred in DB schema | Repo, DB |
| Pulse Endpoints | In repo structure, not in API | Repo, API |
| Webhook Endpoints | In repo structure, not in API | Repo, API |

### Naming Conventions Check

| Convention | Repo Structure | DB Schema | API Contracts | Consistent? |
|------------|---------------|-----------|---------------|-------------|
| Backend folder | `apps/api/` | `backend/` | N/A | NO |
| Pipeline stages | N/A | `audio_generation` | `audio` | NO |
| Alembic location | `apps/api/alembic/` | `backend/alembic/` | N/A | NO |

---

## Recommended Actions

### Priority 1: Critical (Must fix before implementation)

#### 1.1 Add Jobs Table to Database Schema

```sql
-- Jobs table for tracking async pipeline operations
CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,

    -- Job identification
    stage           VARCHAR(50) NOT NULL,  -- planning, scripting, audio, etc.

    -- Status tracking
    status          VARCHAR(50) NOT NULL DEFAULT 'queued',  -- queued, processing, completed, failed, cancelled

    -- Execution details
    worker_id       VARCHAR(100),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    -- Results
    result          JSONB,
    error           TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,

    -- Cost tracking
    cost_usd        DECIMAL(10,4),
    tokens_used     INTEGER,

    -- Configuration
    params          JSONB NOT NULL DEFAULT '{}',

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jobs_episode_id ON jobs(episode_id);
CREATE INDEX idx_jobs_status ON jobs(status) WHERE status IN ('queued', 'processing');
CREATE INDEX idx_jobs_episode_stage ON jobs(episode_id, stage);
```

#### 1.2 Align Episode Status Enum

Standardize on API version (more granular):
```sql
CREATE TYPE episode_status AS ENUM (
    'idea',
    'planning',
    'scripting',
    'script_review',
    'production',
    'assembly',
    'ready',
    'publishing',
    'published',
    'failed',
    'cancelled'
);
```

#### 1.3 Standardize Pipeline Stage Names

Use consistent naming across all documents:
```
planning, scripting, script_review, metadata, audio, avatar, broll, assembly, upload
```

Update database schema `pipeline_state` JSON example to match.

#### 1.4 Add Asset Endpoints to API Contracts

```yaml
## 5.6 List Episode Assets

GET /api/v1/episodes/{episode_id}/assets

## 5.7 Get Asset Details

GET /api/v1/assets/{asset_id}

## 5.8 Get Asset Download URL

GET /api/v1/assets/{asset_id}/download
```

#### 1.5 Add Authentication Endpoints to API Contracts

```yaml
## Authentication Endpoints

POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET /api/v1/auth/me
```

### Priority 2: High (Should fix before implementation)

#### 2.1 Resolve User Model Ambiguity

Option A (Recommended for MVP): Add simplified users table to Phase 1 schema
Option B: Document that Phase 1 uses mock/development auth, user model comes in Phase 2

#### 2.2 Add Channel.niche Column

```sql
ALTER TABLE channels ADD COLUMN niche VARCHAR(100);
CREATE INDEX idx_channels_niche ON channels(niche) WHERE deleted_at IS NULL;
```

#### 2.3 Add Episode Cost Tracking

Option A (Simple, MVP): Add columns to episodes table
```sql
ALTER TABLE episodes ADD COLUMN estimated_cost_usd DECIMAL(10,4);
ALTER TABLE episodes ADD COLUMN actual_cost_usd DECIMAL(10,4) DEFAULT 0;
```

Option B: Move cost_entries table to Phase 1

#### 2.4 Fix Backend Directory Naming

Update database schema document to use `apps/api/` instead of `backend/`

#### 2.5 Add Pulse Event Endpoints

Document webhook and API endpoints for Pulse integration or explicitly mark as Phase 2.

#### 2.6 Add Metadata Pipeline Endpoint

```yaml
POST /api/v1/episodes/{episode_id}/pipeline/metadata
```

### Priority 3: Medium (Fix during implementation)

1. Add episode slug uniqueness constraint per channel
2. Add updated_at triggers to database
3. Remove deprecated Docker Compose version key
4. Add CORS configuration documentation
5. Document mocking strategy for external services in tests
6. Add provider enum validation strategy
7. Document idempotency key storage approach

---

## Overall Assessment

### Strengths

1. **Solid Architectural Foundation** - The documents demonstrate deep understanding of enterprise patterns
2. **Comprehensive Documentation** - Excellent detail level for implementation teams
3. **Future-Proof Design** - Clear extension points for Phase 2+ features
4. **Developer Experience Focus** - Good tooling, clear conventions, helpful examples
5. **Security Awareness** - Proper secrets management, auth patterns, soft deletes

### Areas for Improvement

1. **Cross-Document Consistency** - Several naming and schema mismatches need resolution
2. **Completeness** - Missing jobs table, auth endpoints, asset endpoints
3. **Enum Alignment** - Status and stage enums differ between documents
4. **Phase 1 Scope Clarity** - Some components (users, webhooks) have unclear MVP status

### Final Recommendation

**Proceed to implementation** after addressing Priority 1 critical issues. The architecture is sound and the documents provide sufficient detail for parallel development once the consistency issues are resolved.

Estimated effort to address critical issues: **2-4 hours of documentation updates**

---

## Document Version History

| Version | Date | Reviewer | Summary |
|---------|------|----------|---------|
| 1.0 | 2025-12-05 | Lead Reviewer / QA Engineer | Initial comprehensive review |

---

*This review is part of the ACOG quality assurance process. All findings should be addressed and verified before Phase 1 implementation begins.*
