# AuthentiTrace Complete Technical Documentation

Version: 1.0
Date: 2026-03-13
Project Root: `authenti_trace/`

## 1. Document Purpose and Scope

This document provides complete, implementation-level documentation for the AuthentiTrace codebase currently present in this workspace. It is written as a full technical reference with enough depth to support architecture review, engineering onboarding, implementation handover, and operational runbook usage.

Coverage includes:
- Full backend architecture, service flow, API contracts, data persistence, and security model.
- Full frontend architecture, route-by-route behavior, API interaction, and UX states.
- File-level responsibilities and code-path details.
- Testing strategy and validated behaviors.
- Operational workflow to run the system locally.
- Risks, constraints, and practical next-step recommendations.

This documentation reflects the code as implemented, not an aspirational target design.

## 2. System Overview

AuthentiTrace is a media authenticity verification platform combining:
- A FastAPI backend that ingests media files and computes authenticity/trust through asynchronous multi-signal analysis.
- A tamper-evident ledger (hash chain persisted in SQLite) to guarantee post-verification record integrity.
- A Next.js frontend that supports upload, verification report inspection, and system monitoring/audit.

### 2.1 Core value proposition
- Multi-signal authenticity analysis:
  - Content artifacts
  - Metadata/provenance reality checks
  - Behavioral plausibility
  - Network/OSINT footprint
  - File integrity and blacklist checks
- Deterministic explainable scoring with confidence-aware weighted aggregation.
- Cryptographic chaining of records to detect direct database tampering.
- Audit endpoint to verify full ledger integrity from genesis to tip.

## 3. Repository Structure

Top-level observed structure:
- `backend/`: FastAPI API, scoring and signal logic, ledger persistence, tests.
- `frontend/`: Next.js app-router UI for upload/report/dashboard.
- `storage/`: Media upload storage target created/used by backend upload pipeline.
- `architecture/`: currently empty.
- `tools/`: currently present but not populated in reviewed source.
- Documentation control files:
  - `task_plan.md`
  - `progress.md`
  - `findings.md`
  - `claude.md`
  - `gemini.md`

Notable state:
- `architecture/`, `findings.md`, `claude.md`, and `gemini.md` are scaffolds/placeholders and do not yet contain final operating standards.

## 4. Runtime Architecture

### 4.1 High-level flow
1. User uploads media from frontend `upload` page.
2. Backend validates MIME and size, streams file to disk, computes SHA-256.
3. Backend runs all signal plugins concurrently.
4. Scoring engine computes weighted trust score and enforcement decision.
5. Result is committed to hash-chained ledger row in SQLite.
6. API returns explainable report with telemetry and ledger hashes.
7. Frontend redirects to report page and displays trust breakdown.
8. Dashboard can retrieve aggregate metrics and run full chain integrity audit.

### 4.2 Key technologies
Backend:
- FastAPI
- SQLAlchemy Async ORM
- SQLite with `aiosqlite`
- Pydantic v2 models
- Uvicorn

Frontend:
- Next.js App Router
- React 19
- TypeScript
- Native fetch API

## 5. Backend Detailed Design

### 5.1 App entrypoint
File: `backend/app/main.py`

Responsibilities:
- Defines FastAPI app metadata and lifecycle.
- Creates DB tables on startup via async engine.
- Disposes DB engine on shutdown.
- Configures CORS for local frontend origins:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- Registers route groups:
  - `/api/v1/upload`
  - `/api/v1/reports`
  - `/api/v1/dashboard`

Lifecycle behavior:
- Startup: `Base.metadata.create_all` called once against configured DB.
- Shutdown: engine disposed.

### 5.2 Dependency and DB session wiring
File: `backend/app/database/database.py`

Implementation details:
- DB URL: `sqlite+aiosqlite:///./authentitrace.db`
- Async engine with `echo=False`.
- AsyncSession factory via `async_sessionmaker`.
- `get_db()` dependency yields one async session per request.

Operational implication:
- Relative path database file resolved from backend process working directory.
- Local DB persistence is file-based SQLite, suitable for development and low-throughput environments.

### 5.3 Data model
File: `backend/app/models/ledger.py`

#### `VerificationRecord` table: `verification_ledger`
Fields:
- `id` (PK, UUID string)
- `media_reference_id` (index)
- `file_hash` (required)
- `composite_score` (float)
- `risk_category` (string)
- `enforcement_action` (string)
- `signal_telemetry` (JSON)
- `previous_hash` (required)
- `current_hash` (required)
- `created_at` (UTC datetime default)

Role:
- Stores one immutable verification result and chain-link metadata.

#### `SignalWeight` table: `signals_weight`
Fields:
- `id` (PK)
- `signal_name` (unique/indexed)
- `current_weight`
- `updated_at`

Current usage:
- Present in schema but not actively read by scoring pipeline (static in-code weights are used today).

### 5.4 API schemas
File: `backend/app/schemas/verification.py`

Key models:
- `SignalResult`
  - plugin identity, score [0-100], confidence [0-1], reasoning, metadata
- `ScoringResult`
  - trust score, risk category, enforcement action
- `ReportResponse`
  - full persisted ledger/report payload
- `MediaUploadResponse`
  - defined but not currently used by upload endpoint response contract

Pydantic config:
- `ReportResponse` uses `from_attributes=True` for ORM model validation.

## 6. Backend Endpoint-by-Endpoint Documentation

### 6.1 Upload and verify endpoint
File: `backend/app/api/v1/endpoints/upload.py`
Route: `POST /api/v1/upload/`
Response model: `ReportResponse`

Request:
- `multipart/form-data` with `file`

Behavior sequence:
1. `save_upload_and_hash(file)` performs storage + validation + SHA computation.
2. `process_verification(...)` runs signals, scoring, and ledger commit.
3. Returns persisted report row mapped to schema.

Error handling:
- Explicitly rethrows known `HTTPException`.
- Wraps unknown exceptions into `500 Internal Server Error` with detail string.

### 6.2 Reports endpoint
File: `backend/app/api/v1/endpoints/reports.py`
Route: `GET /api/v1/reports/{ledger_id}`

Behavior:
- Queries `VerificationRecord` by primary key.
- Returns `404` if not found.
- Returns full report object if found.

### 6.3 Dashboard metrics endpoint
File: `backend/app/api/v1/endpoints/dashboard.py`
Route: `GET /api/v1/dashboard/metrics`

Behavior:
- Loads all records.
- Computes:
  - `total_verifications`
  - `risk_distribution` with keys `LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`

### 6.4 Ledger audit endpoint
File: `backend/app/api/v1/endpoints/dashboard.py`
Route: `GET /api/v1/dashboard/audit`

Algorithm:
1. Load all records ordered by ascending `created_at`.
2. Initialize `previous_hash` with genesis constant.
3. Reconstruct canonical payload from each row values.
4. Recompute expected hash with `calculate_ledger_hash`.
5. Compare expected hash to persisted `current_hash`.
6. Collect mismatch errors and boolean integrity flag.

Response:
- `ledger_intact`: true/false
- `chain_length`: number of blocks
- `errors`: array of textual mismatch descriptions

Security property:
- Detects tampering of historical rows when row data changes without synchronized hash recomputation.

## 7. Verification Pipeline Internals

### 7.1 Media ingestion and hash computation
File: `backend/app/services/media_service.py`

Validation and storage rules:
- Allowed MIME:
  - `image/jpeg`
  - `image/png`
  - `image/webp`
  - `video/mp4`
  - `audio/mpeg`
- Max file size: 50 MB
- Storage directory: `./storage` (auto-created)

Implementation details:
- Uses streamed chunk writes (`1 MB` per chunk) through `aiofiles`.
- Computes SHA-256 incrementally while writing.
- Enforces hard size limit during stream.
- On overflow, attempts cleanup by deleting partially written file and throws `413`.
- Returns `(media_id, file_path, file_hash)`.

Operational note:
- File extension is inferred from filename suffix and not from binary signature.
- Inline comment indicates production intent to use strict binary type verification.

### 7.2 Orchestration service
File: `backend/app/services/verification_service.py`

Pipeline stages:
- Defines active plugin set:
  - `ContentSignal`
  - `RealitySignal`
  - `BehavioralSignal`
  - `NetworkSignal`
  - `IntegritySignal`
- Executes all plugin `analyze` calls via `asyncio.gather` concurrently.
- Builds telemetry map keyed by plugin name.
- Calculates weighted score through scoring engine.
- Persists result through ledger service.
- Returns validated report object.

Current weight strategy:
- Static in-code weights:
  - Content: 1.5
  - Reality: 1.0
  - Behavioral: 1.2
  - Network: 0.8
  - Integrity: 1.3

## 8. Signal Plugins (Per-Plugin Logic)

### 8.1 Signal contract
File: `backend/app/signals/base.py`

All plugins must implement:
- `name` property
- `analyze(media_path: str, file_hash: str) -> SignalResult` async method

### 8.2 ContentSignal
File: `backend/app/signals/content.py`

Observed heuristic:
- Reads file size for metadata.
- Uses first 4 hex chars of file hash to derive deterministic pseudo-random anomaly score.
- Maps anomaly ranges to score/confidence/reason buckets.

Typical outputs:
- High anomaly: score ~30, confidence 0.88
- Medium anomaly: score ~65, confidence 0.75
- Low anomaly: score ~95, confidence 0.92

### 8.3 RealitySignal
File: `backend/app/signals/reality.py`

Observed heuristic:
- Uses hash slice [8:12] to simulate provenance signal.
- Simulates C2PA presence probability.

Output branches:
- C2PA present: score 100, confidence 0.99
- Missing/stripped provenance: score 40, confidence 0.70

### 8.4 BehavioralSignal
File: `backend/app/signals/behavioral.py`

Observed heuristic:
- For still images (`.jpg`, `.jpeg`, `.png`): returns pose-only limited assessment.
- For motion media: uses hash slice [4:8] to derive sync error.
- High sync error penalized heavily.

### 8.5 NetworkSignal
File: `backend/app/signals/network.py`

Observed heuristic:
- Uses hash slice [12:16] to emulate OSINT propagation matches.
- Higher matches imply likely malicious or coordinated propagation.

### 8.6 IntegritySignal
File: `backend/app/signals/integrity.py`

Critical control behavior:
- Recomputes real SHA-256 from saved file bytes.
- If recomputed hash != expected hash, returns absolute failure score 0/confidence 1.
- Simulates blacklist check via prefix rule (`file_hash.startswith("0000")`).

Security importance:
- Only plugin performing direct cryptographic validation over bytes currently on disk.

## 9. Scoring Engine and Enforcement Policy

File: `backend/app/services/scoring_engine.py`

### 9.1 Formula
For each signal:
- `base_weight = weights[plugin_name]` or `1.0`
- `effective_weight = base_weight * confidence`
- accumulate `score * effective_weight`

Final score:
- weighted mean = `sum(score*effective_weight) / sum(effective_weight)`
- rounded to 2 decimals

### 9.2 Critical failure gate
Rule:
- If any signal has `score < 10` and `confidence > 0.9`, mark critical failure.
- Cap final score at `20.0`.

Impact:
- Prevents high confidence catastrophic findings from being diluted by otherwise high scores.

### 9.3 Risk/action thresholds
- Score `< 40`:
  - `HIGH_RISK`
  - `RESTRICT`
- Score `< 75`:
  - `MEDIUM_RISK`
  - `FLAG`
- Else:
  - `LOW_RISK`
  - `APPROVE`

## 10. Tamper-Evident Ledger Design

### 10.1 Hashing primitive
File: `backend/app/utils/security.py`

`calculate_ledger_hash(previous_hash, payload)`:
- JSON canonicalization with sorted keys and compact separators.
- Hash input string format: `"{previous_hash}|{canonical_payload_json}"`.
- SHA-256 output hex digest.

This guarantees deterministic hash generation across equivalent payloads.

### 10.2 Ledger commit sequence
File: `backend/app/services/ledger_service.py`

1. Read latest row by `created_at DESC`.
2. If none found, use genesis hash (`64` zeros).
3. Build canonical payload fields:
  - media id
  - file hash
  - score formatted to 2 decimals string
  - risk
  - action
  - telemetry
4. Compute `current_hash` from `previous_hash + payload`.
5. Insert row and commit transaction.
6. Refresh and return inserted row.

### 10.3 Integrity properties and limitations
Properties:
- Any post-hoc edit to row content breaks future audit recomputation.
- Every row links to predecessor hash forming a linear chain.

Limitations in current implementation:
- SQLite + optimistic read of latest row can be race-prone under concurrent writes.
- Code comment already flags recommendation for row lock semantics in production databases (e.g., PostgreSQL).

## 11. Frontend Detailed Design

### 11.1 Application shell
File: `frontend/src/app/layout.tsx`

Features:
- Global navigation with links:
  - `/upload`
  - `/dashboard`
- Metadata:
  - title `AuthentiTrace`
  - description `Multi-Signal Media Trust Infrastructure`

### 11.2 Landing page
File: `frontend/src/app/page.tsx`

Purpose:
- Product positioning and quick entry links.
- Static marketing/summary card layout for engine, ledger, explainability.

### 11.3 Upload page
File: `frontend/src/app/upload/page.tsx`

Behavior:
- File input selection and validation for empty state.
- Sends `multipart/form-data` to `http://localhost:8000/api/v1/upload/`.
- On success: navigates to `/report/{report.id}`.
- On error: displays message and retains page context.
- Displays loading spinner and analysis text while request in progress.

### 11.4 Report page
File: `frontend/src/app/report/[id]/page.tsx`

Behavior:
- Reads dynamic route parameter `id`.
- Fetches report from `http://localhost:8000/api/v1/reports/{id}`.
- Renders:
  - Overall risk badge
  - Composite trust score
  - Ledger receipt values
  - Signal-by-signal telemetry cards

### 11.5 Dashboard page
File: `frontend/src/app/dashboard/page.tsx`

Behavior:
- Fetches metrics and audit endpoints in parallel.
- Renders total verification count.
- Renders audit status (`SECURE` or `TAMPER DETECTED`).
- Displays chain length and first error if present.
- Renders risk-distribution bars as percentages.

### 11.6 Styling model
File: `frontend/src/app/globals.css`

Features:
- Dark visual theme variables.
- Glass panel style components.
- Shared button, navigation, spinner, and badge classes.
- Responsive behavior is basic and mostly handled by CSS grids/flex with auto-fit.

Additional file state:
- `frontend/src/app/page.module.css` appears to be boilerplate and is not referenced by current `page.tsx` implementation.

## 12. API Contract Summary

### 12.1 `POST /api/v1/upload/`
Input:
- form-data: `file`

Success response (shape):
- `id`
- `media_reference_id`
- `file_hash`
- `composite_score`
- `risk_category`
- `enforcement_action`
- `signal_telemetry`
- `previous_hash`
- `current_hash`
- `created_at`

Failure responses:
- `413` file too large
- `415` unsupported MIME type
- `500` unexpected internal error

### 12.2 `GET /api/v1/reports/{ledger_id}`
- `200` with report payload
- `404` if missing

### 12.3 `GET /api/v1/dashboard/metrics`
- total and risk distribution summary

### 12.4 `GET /api/v1/dashboard/audit`
- ledger integrity state and detailed mismatch list

## 13. Security Analysis

### 13.1 Strong points
- SHA-256 file hashing and deterministic ledger chaining.
- Explicit chain audit endpoint.
- Confidence-aware and critical-failure-aware scoring policy.
- Input size and MIME validation in upload pipeline.

### 13.2 Risks and gaps
- MIME check uses declared content type; binary sniffing not yet implemented.
- No authentication/authorization around APIs.
- CORS restricted to localhost, but no production origin management layer.
- Upload cleanup for large files relies on manual delete path and could be hardened.
- SQLite is not ideal for high-concurrency ledger writes.
- Error responses in upload endpoint expose internal exception text.

### 13.3 Hardening recommendations
- Add byte-level file type verification (libmagic or equivalent).
- Introduce API auth (JWT/OAuth2/API key based on target deployment).
- Replace SQLite with PostgreSQL and add proper write-lock/transaction semantics.
- Add structured error model without leaking internals.
- Add rate-limiting and body size constraints at reverse proxy layer.

## 14. Performance and Scalability

Current characteristics:
- Signals execute concurrently inside one request context via `asyncio.gather`.
- SQLite can become bottleneck for write-heavy loads.
- Integrity plugin reads full file into memory (`f.read()`), which can be expensive for large media.

Optimization opportunities:
- Streamed file hashing in integrity plugin to avoid full-memory read.
- Queue-based async processing for large jobs and non-blocking UI polling.
- Use object storage and content-addressable references for media retention.
- Add caching or incremental metrics aggregation for dashboard endpoints.

## 15. Testing and Quality

File: `backend/tests/test_ledger.py`

Covered cases:
- Genesis hash retrieval for empty DB.
- Proper chain linking across two commits.
- Tamper detection by modifying persisted row and re-verifying hash mismatch.

Current gaps:
- No API endpoint tests.
- No media validation tests.
- No signal scoring boundary tests.
- No frontend tests (unit, integration, or E2E).

Recommended test roadmap:
- Add `pytest` API tests with `httpx` and temporary DB fixture.
- Add scoring threshold and critical-failure boundary tests.
- Add upload tests for MIME/size behavior and cleanup.
- Add Playwright-based frontend E2E for upload to report and dashboard audit flow.

## 16. Build, Run, and Operations

### 16.1 Backend local run
From `backend/`:
- Install deps from `requirements.txt`
- Run Uvicorn app module

### 16.2 Frontend local run
From `frontend/`:
- `npm install`
- `npm run dev`

### 16.3 End-to-end local URL map
- Frontend: `http://localhost:3000`
- Backend OpenAPI docs: `http://localhost:8000/docs`
- API base used by frontend: `http://localhost:8000/api/v1/...`

## 17. File-by-File Responsibility Matrix

Backend core:
- `backend/app/main.py`: app lifecycle, CORS, route registration.
- `backend/app/database/database.py`: async engine/session factory/dependency.
- `backend/app/models/ledger.py`: ledger and signal weight ORM entities.
- `backend/app/schemas/verification.py`: Pydantic contracts.

Backend endpoints:
- `backend/app/api/v1/endpoints/upload.py`: upload + full verification trigger.
- `backend/app/api/v1/endpoints/reports.py`: report retrieval by ID.
- `backend/app/api/v1/endpoints/dashboard.py`: metrics and chain audit.

Backend services:
- `backend/app/services/media_service.py`: stream-save and hash media files.
- `backend/app/services/verification_service.py`: orchestrate plugins/scoring/commit.
- `backend/app/services/scoring_engine.py`: weighted trust + enforcement rules.
- `backend/app/services/ledger_service.py`: hash chain read/write operations.

Backend signals:
- `backend/app/signals/base.py`: plugin interface.
- `backend/app/signals/content.py`: content anomaly heuristic.
- `backend/app/signals/reality.py`: provenance/metadata heuristic.
- `backend/app/signals/behavioral.py`: motion and sync plausibility heuristic.
- `backend/app/signals/network.py`: network propagation heuristic.
- `backend/app/signals/integrity.py`: byte-level hash verification and blacklist heuristic.

Backend utilities and tests:
- `backend/app/utils/security.py`: deterministic SHA hash helpers.
- `backend/tests/test_ledger.py`: chain correctness and tamper detection tests.

Frontend:
- `frontend/src/app/layout.tsx`: app shell and nav.
- `frontend/src/app/page.tsx`: landing page.
- `frontend/src/app/upload/page.tsx`: upload and verification request flow.
- `frontend/src/app/report/[id]/page.tsx`: report detail renderer.
- `frontend/src/app/dashboard/page.tsx`: metrics and integrity dashboard.
- `frontend/src/app/globals.css`: global styles and reusable class tokens.

## 18. Observed Inconsistencies and Technical Debt

- `calculate_file_hash` utility exists but upload service computes hash inline and does not use it.
- `MediaUploadResponse` schema exists but upload endpoint returns `ReportResponse`.
- `SignalWeight` ORM table exists but runtime weights are static dictionary.
- `page.module.css` appears unused by current app pages.
- Some textual labels indicate prototype language (for example simulated model notes) rather than strict production-facing terminology.

## 19. Governance, Documentation Rules, and 20-Page Preparation Standard

Because the in-repo rule files are placeholders, the following standards are established for ongoing documentation quality and review consistency:

1. Source-of-truth rule
- Every claim must map directly to an existing file/function/route in this repository.

2. Determinism rule
- For scoring, hashes, and thresholds, document formulas and exact constants.

3. Security-first rule
- Every endpoint and storage flow must include a threat/risk note.

4. Contract-completeness rule
- Every API endpoint must include method, path, input shape, and failure modes.

5. Traceability rule
- Every architecture section must include file references.

6. Testability rule
- For each major component, list at least one existing test and one missing critical test.

7. Operations rule
- Include exact local run path assumptions and host/port mapping.

8. Change management rule
- Any behavior change must update this documentation and `progress.md` in the same change set.

## 20. Suggested Near-Term Execution Plan

Phase A: Security hardening
- Add binary-type validation and auth.
- Remove internal exception leakage.

Phase B: Data integrity robustness
- Move to PostgreSQL, add serializable transaction handling for ledger writes.
- Add migration management tooling.

Phase C: Product maturity
- Convert simulated signals to real model/service integrations.
- Add asynchronous job queue for long media verification.

Phase D: Quality expansion
- Add full API tests + E2E frontend tests.
- Add lint/test CI pipeline and release gates.

## 21. Operational Runbook Quick Reference

Start sequence:
1. Backend on 8000.
2. Frontend on 3000.
3. Open browser at `http://localhost:3000`.
4. Upload media and verify redirect to report view.
5. Validate dashboard audit state.

Validation checklist:
- Upload returns report object and redirects.
- Report page loads signal telemetry cards.
- Dashboard metrics increments with each successful upload.
- Audit endpoint remains `ledger_intact=true` unless DB tampered.

## 22. Conclusion

The current AuthentiTrace codebase already implements the main conceptual architecture: multi-signal authenticity scoring with explainable telemetry and a cryptographically chained audit trail. It is a strong functional prototype with clear internal separation between ingestion, orchestration, scoring, ledger persistence, and presentation.

Primary production readiness work remains in four areas:
- security controls,
- concurrency and persistence robustness,
- broader test coverage,
- integration of real signal engines.

With those enhancements, the platform can progress from prototype-grade to enterprise-deployable verification infrastructure.

## 23. Data Dictionary and Field Semantics

### 23.1 `verification_ledger` dictionary

`id`
- Meaning: globally unique row identifier for a verification event.
- Source: generated UUID when SQLAlchemy model is instantiated.
- Consumer: frontend report retrieval path parameter via `/reports/{id}`.

`media_reference_id`
- Meaning: upload-session identifier tied to stored file artifact.
- Source: generated UUID in upload service.
- Consumer: report display and operational traceability.

`file_hash`
- Meaning: SHA-256 digest of uploaded bytes during ingestion stream.
- Source: upload stream hashing pipeline.
- Consumer: report receipt, integrity plugin validation, audit reconstruction.

`composite_score`
- Meaning: weighted trust score from all active signals.
- Source: scoring engine output.
- Consumer: risk badge logic, dashboard distribution and enforcement state.

`risk_category`
- Allowed values (observed): `LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`.
- Source: scoring threshold mapping.
- Consumer: dashboard counters and report badge styling.

`enforcement_action`
- Allowed values (observed): `APPROVE`, `FLAG`, `RESTRICT`.
- Source: scoring policy branch.
- Consumer: operational interpretation of risk posture.

`signal_telemetry`
- Meaning: structured details for each plugin result.
- Structure: map keyed by plugin name, value = serialized `SignalResult`.
- Consumer: report telemetry cards and audit hash recomputation payload.

`previous_hash`
- Meaning: parent link in chain.
- Source: latest persisted `current_hash` or genesis constant.

`current_hash`
- Meaning: SHA-256 over canonical payload plus previous hash.
- Source: ledger hash function in commit service.

`created_at`
- Meaning: UTC timestamp of insertion.
- Source: default lambda at ORM model level.
- Consumer: ordering in audit walk and timeline interpretation.

### 23.2 `SignalResult` telemetry dictionary

`plugin_name`
- Stable identifier of source plugin.

`score`
- Numeric trust contribution signal in range 0..100.

`confidence`
- Confidence in score quality in range 0..1.
- Used to scale effective weight.

`reasoning`
- Human-readable summary of why score was produced.

`metadata`
- Plugin-specific structured fields for advanced diagnostics.

## 24. End-to-End Request Sequence Narratives

### 24.1 Upload verification sequence

1. Browser selects media file at `frontend/src/app/upload/page.tsx`.
2. Client sends `multipart/form-data` to `/api/v1/upload/`.
3. FastAPI endpoint resolves DB dependency and starts async execution.
4. Upload service validates MIME type against allowed list.
5. Upload service streams bytes to `./storage/{media_id}.{ext}` while hashing.
6. Upload service enforces hard 50 MB limit during stream loop.
7. Orchestrator starts all plugins concurrently with shared `file_path` and `file_hash`.
8. Each plugin returns `SignalResult` payload.
9. Scoring engine computes confidence-weighted composite score.
10. Ledger service retrieves latest chain tip hash.
11. Ledger service computes new row hash and commits DB transaction.
12. Endpoint returns `ReportResponse`.
13. Frontend route transitions to `/report/{id}` and loads report view.

### 24.2 Dashboard audit sequence

1. Dashboard page calls `/metrics` and `/audit` concurrently.
2. Audit endpoint loads rows ordered oldest-first.
3. Server initializes previous hash to genesis.
4. For each row, canonical payload is reconstructed.
5. Expected hash is recomputed and compared.
6. Mismatch events are accumulated into error list.
7. Result returned with `ledger_intact` and `chain_length`.
8. Frontend shows secure/tampered state badge and first error if any.

## 25. Failure Mode and Effects Analysis (FMEA)

### 25.1 Ingestion failures

Unsupported content type:
- Detection: content-type not in allowed set.
- Result: `415`.
- User impact: upload rejected immediately.
- Mitigation: allowlist management and better UX hints.

File too large:
- Detection: stream byte count exceeds 50 MB.
- Result: `413` and delete partial file.
- User impact: upload canceled after partial transfer.
- Mitigation: preflight size check on frontend and resumable upload architecture for future.

Disk write failure:
- Detection: exceptions from `aiofiles` operations.
- Result: falls to generic `500` path.
- Mitigation: storage health checks, free-space alerting, robust retry logic.

### 25.2 Verification failures

Plugin crash:
- Detection: exception inside `asyncio.gather` context.
- Result: request fails (current mode does not isolate failed plugin).
- Mitigation: gather with `return_exceptions=True` and degrade gracefully.

Confidence/weight anomalies:
- Detection: low effective aggregate weight.
- Result: potentially unstable composite score.
- Mitigation: minimum total effective weight guardrails and policy fallback.

### 25.3 Ledger failures

Concurrent commit race:
- Detection: non-linear chain relationships under load.
- Result: possible branching or unexpected parent link under high concurrency.
- Mitigation: database transactional locking and serialized writer model.

Tampering event:
- Detection: `/dashboard/audit` mismatch.
- Result: `ledger_intact=false` and explicit mismatch text.
- Mitigation: alerting, incident response, immutable backups.

## 26. API Examples (Concrete)

### 26.1 Upload request example

```bash
curl -X POST "http://localhost:8000/api/v1/upload/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.mp4"
```

Example success response (shape excerpt):

```json
{
  "id": "2ec5f4fd-f4f4-4f22-b24a-7f16b2f3d14f",
  "media_reference_id": "454fbd42-52f9-4574-bf5b-87f64573f5d7",
  "file_hash": "9c3436...",
  "composite_score": 72.14,
  "risk_category": "MEDIUM_RISK",
  "enforcement_action": "FLAG",
  "signal_telemetry": {
    "ContentSignal": {"plugin_name": "ContentSignal", "score": 65.0, "confidence": 0.75, "reasoning": "...", "metadata": {}},
    "RealitySignal": {"plugin_name": "RealitySignal", "score": 40.0, "confidence": 0.70, "reasoning": "...", "metadata": {}},
    "BehavioralSignal": {"plugin_name": "BehavioralSignal", "score": 90.0, "confidence": 0.82, "reasoning": "...", "metadata": {}},
    "NetworkSignal": {"plugin_name": "NetworkSignal", "score": 75.0, "confidence": 0.60, "reasoning": "...", "metadata": {}},
    "IntegritySignal": {"plugin_name": "IntegritySignal", "score": 100.0, "confidence": 0.99, "reasoning": "...", "metadata": {}}
  },
  "previous_hash": "000000...",
  "current_hash": "15e74d...",
  "created_at": "2026-03-13T11:25:21.442331+00:00"
}
```

### 26.2 Report retrieval example

```bash
curl "http://localhost:8000/api/v1/reports/2ec5f4fd-f4f4-4f22-b24a-7f16b2f3d14f"
```

### 26.3 Dashboard metrics example

```bash
curl "http://localhost:8000/api/v1/dashboard/metrics"
```

Example response:

```json
{
  "total_verifications": 43,
  "risk_distribution": {
    "LOW_RISK": 20,
    "MEDIUM_RISK": 16,
    "HIGH_RISK": 7
  }
}
```

### 26.4 Dashboard audit example

```bash
curl "http://localhost:8000/api/v1/dashboard/audit"
```

Example response:

```json
{
  "ledger_intact": true,
  "chain_length": 43,
  "errors": []
}
```

## 27. Frontend UX States and Behavior Contract

### 27.1 Upload page states

Initial state:
- No file selected.
- CTA disabled until file selected.

Selected state:
- Shows file name and approximate MB size.
- Upload CTA enabled.

Processing state:
- Spinner visible.
- Analysis text displayed.
- Input controls hidden.

Error state:
- Displays error text in danger color.
- User can reselect file and retry.

### 27.2 Report page states

Loading state:
- Spinner only.

Error state:
- Glass panel with error message when report not found/fetch failed.

Success state:
- Risk badge + score card + ledger hashes + telemetry cards.

### 27.3 Dashboard states

Loading state:
- Spinner.

Success state:
- Metrics cards and bars.

Audit-negative state:
- Tamper warning marker and first error text presented.

## 28. Security Threat Model Snapshot

Assets:
- Original media file bytes.
- Verification telemetry and scores.
- Ledger hash chain consistency.

Threat actors:
- External unauthenticated API caller.
- Insider with direct DB write access.
- User attempting malformed/oversized uploads.

Attack surfaces:
- Upload endpoint.
- Report and dashboard endpoints.
- Local file storage.
- Database file tampering.

Threats and controls (current):
- Oversized upload DoS: partial control via size cap.
- MIME spoofing: weak control (header-based only).
- Ledger tampering: detection control via hash audit.
- Unauthorized API access: no control implemented yet.

Threats and controls (recommended):
- Add authN/authZ for all non-public routes.
- Add API rate limiting and reverse-proxy limits.
- Add object storage with signed URL ingestion.
- Add SIEM/alerts for audit mismatch conditions.

## 29. Deployment Blueprint (Practical)

### 29.1 Environment split recommendation

Development:
- SQLite, local disk storage, direct localhost CORS.

Staging:
- PostgreSQL, object storage bucket, managed secrets, internal auth.

Production:
- PostgreSQL HA, durable object storage, WAF/rate-limits, centralized logging.

### 29.2 Suggested infra components

- API service (FastAPI + Uvicorn workers).
- Frontend service (Next.js, edge/cache where appropriate).
- Relational DB (PostgreSQL).
- Object storage for media blobs.
- Queue worker for heavy async verification jobs.
- Metrics/logging stack and alerting.

### 29.3 Operational SLO suggestions

- P95 upload API latency under target threshold per file size class.
- Dashboard endpoints under 500 ms at normal load.
- Audit run completes within expected bounded time for chain size.
- Error budget tied to 5xx rate and ingestion failure anomalies.

## 30. Troubleshooting Manual

Backend does not start:
- Check Python and virtual environment activation.
- Verify dependencies from `backend/requirements.txt`.
- Confirm working directory is `backend/` so import path `app.main` resolves.

Frontend does not start:
- Run `npm install` in `frontend/`.
- Confirm Node version supports Next.js 16.

Upload fails with `415`:
- Verify selected file type is in allowlist.

Upload fails with `413`:
- File exceeds 50 MB hard limit.

Report page shows not found:
- Verification request may have failed before commit.
- Confirm backend logs and API response status.

Audit shows tampering:
- Compare row payload and `current_hash` for first mismatch ID.
- Investigate direct DB writes or migration side effects.

## 31. Validation Checklist for Release Readiness

Functional:
- Upload verifies and returns report consistently.
- Report page renders all 5 signal cards.
- Dashboard metrics and audit update correctly.

Security:
- MIME binary checks implemented.
- Auth applied to sensitive endpoints.
- Error responses sanitized.

Data integrity:
- Chain integrity remains true under normal operations.
- Tamper simulation correctly flips audit to false.

Performance:
- Baseline load tests for upload and dashboard endpoints.
- File hashing memory profile verified for large accepted files.

Testing:
- Unit + integration + E2E suites pass in CI.

## 32. Engineering Backlog (Prioritized)

Priority 1:
- Add authentication and authorization.
- Introduce robust MIME sniffing.
- Add endpoint integration tests.

Priority 2:
- Move scoring weights to DB-backed configuration table.
- Add admin controls for weight tuning and audit trail.
- Add pagination/filtering for reports listing endpoint (new route).

Priority 3:
- Convert plugin mocks to external ML services with explicit SLA and timeout strategy.
- Add async job processing for long-running media classes.

Priority 4:
- Add localization and accessibility enhancements to frontend.
- Add observability dashboard and anomaly alerts.

## 33. Documentation Maintenance SOP

When backend endpoint behavior changes:
- Update API section, examples, and failure tables.

When scoring logic changes:
- Update formula, thresholds, and enforcement mapping section.

When data model changes:
- Update data dictionary and matrix section.

When frontend flow changes:
- Update route behavior and state machine descriptions.

When run scripts/automation change:
- Update operational runbook and startup instructions.

## 34. Glossary

Audit chain:
- Sequence of ledger records where each row hash includes parent hash.

C2PA:
- Coalition for Content Provenance and Authenticity standard for provenance metadata.

Composite score:
- Weighted trust score aggregated from all signal outputs.

Effective weight:
- `base_weight * confidence` in scoring logic.

Genesis hash:
- Initial parent hash value used for first ledger row.

Signal telemetry:
- Full per-plugin output details stored with each report.

Tamper-evident:
- Design where unauthorized modifications are detectable via cryptographic checks.

## 35. Final Reference Index

Backend entry and routing:
- `backend/app/main.py`

Persistence and models:
- `backend/app/database/database.py`
- `backend/app/models/ledger.py`

Schema contracts:
- `backend/app/schemas/verification.py`

Endpoints:
- `backend/app/api/v1/endpoints/upload.py`
- `backend/app/api/v1/endpoints/reports.py`
- `backend/app/api/v1/endpoints/dashboard.py`

Services:
- `backend/app/services/media_service.py`
- `backend/app/services/verification_service.py`
- `backend/app/services/scoring_engine.py`
- `backend/app/services/ledger_service.py`

Signals:
- `backend/app/signals/base.py`
- `backend/app/signals/content.py`
- `backend/app/signals/reality.py`
- `backend/app/signals/behavioral.py`
- `backend/app/signals/network.py`
- `backend/app/signals/integrity.py`

Security utilities and tests:
- `backend/app/utils/security.py`
- `backend/tests/test_ledger.py`

Frontend app:
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/upload/page.tsx`
- `frontend/src/app/report/[id]/page.tsx`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/globals.css`

Configuration and package metadata:
- `backend/requirements.txt`
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/eslint.config.mjs`
- `frontend/next.config.ts`
