# AuthentiTrace Routing Deep Dive

This document explains every routing layer in AuthentiTrace:

1. Frontend page routing (Next.js App Router)
2. Frontend navigation and dynamic route behavior
3. Backend API routing (FastAPI routers)
4. End-to-end unique report ID flow
5. Code-level explanations for each step

## 1. Frontend Route Map (Next.js App Router)

The app uses folder-based routing under `frontend/src/app`:

- `frontend/src/app/page.tsx` -> `/`
- `frontend/src/app/upload/page.tsx` -> `/upload`
- `frontend/src/app/dashboard/page.tsx` -> `/dashboard`
- `frontend/src/app/report/[id]/page.tsx` -> `/report/:id` (dynamic)

### Why this matters

- Routing is deterministic from the file system.
- Dynamic segment `[id]` creates one URL per report.
- Direct deep links are supported (open `/report/some-id` directly).

## 2. Global Navigation Routing

Navigation links are defined in `frontend/src/app/layout.tsx`:

- Home link points to `/`
- Verify Media link points to `/upload`
- Dashboard link points to `/dashboard`

Code concept:

- `Link href="/upload"` triggers client-side route transitions.
- No full page reload is needed for normal navigation between pages.

## 3. API URL Routing Helper

File: `frontend/src/lib/api.ts`

The helper function `apiUrl(path)` builds endpoint URLs consistently.

Current behavior:

- If `NEXT_PUBLIC_API_URL` is defined, requests go to that backend base.
- In development, fallback base is `http://localhost:8000`.
- In production without explicit base, paths remain relative.

This prevents hardcoded localhost issues in deployed environments.

## 4. Upload Page Route Transition to Dynamic Report

File: `frontend/src/app/upload/page.tsx`

Important routing logic:

1. User uploads media to `POST /api/v1/upload/`.
2. Backend returns a report object that includes `report.id`.
3. Frontend executes:
   - ``router.push(`/report/${report.id}`)``

This is the key dynamic routing handoff.

## 5. Dynamic Report Route Consumption

File: `frontend/src/app/report/[id]/page.tsx`

Important route logic:

1. Page reads route parameter via `useParams()`.
2. Extracts `reportId` from `id`.
3. Calls backend endpoint:
   - `GET /api/v1/reports/{reportId}`
4. Renders telemetry, score, and ledger details for that exact record.

Error path handling:

- Missing route id -> shows "Invalid report id"
- Missing backend record -> backend returns 404 and page shows error

## 6. Dashboard Page Route Behavior

File: `frontend/src/app/dashboard/page.tsx`

When route `/dashboard` loads:

1. Fetches metrics route:
   - `GET /api/v1/dashboard/metrics`
2. Fetches audit route:
   - `GET /api/v1/dashboard/audit`
3. Renders status cards and risk distribution.

Both requests are resolved in parallel with `Promise.allSettled`.

## 7. Backend API Route Map

Defined in `backend/app/main.py`:

- Upload router mounted at `/api/v1/upload`
- Reports router mounted at `/api/v1/reports`
- Dashboard router mounted at `/api/v1/dashboard`

### Concrete endpoint paths

Upload endpoint:
- File: `backend/app/api/v1/endpoints/upload.py`
- `POST /api/v1/upload/`

Report by ID endpoint:
- File: `backend/app/api/v1/endpoints/reports.py`
- `GET /api/v1/reports/{ledger_id}`

Dashboard endpoints:
- File: `backend/app/api/v1/endpoints/dashboard.py`
- `GET /api/v1/dashboard/metrics`
- `GET /api/v1/dashboard/audit`

## 8. Unique ID Generation and Routing Lifecycle

You mentioned the best part: every result has a unique route ID.

Here is the full lifecycle:

### Step A: Upload receives a unique media reference

File: `backend/app/services/media_service.py`

- `media_id = str(uuid.uuid4())`
- This identifies the uploaded media file.

### Step B: Ledger row gets its own unique report ID

File: `backend/app/models/ledger.py`

- `VerificationRecord.id` is primary key
- Default value comes from `generate_uuid()`
- `generate_uuid()` returns `str(uuid.uuid4())`

So each saved report has a unique ledger ID independent of media filename.

### Step C: Upload API returns the report object

File: `backend/app/api/v1/endpoints/upload.py`

- Calls verification pipeline and persists record.
- Returns `ReportResponse` containing `id`.

### Step D: Frontend routes to unique report page

File: `frontend/src/app/upload/page.tsx`

- ``router.push(`/report/${report.id}`)``

### Step E: Dynamic page resolves by ID

File: `frontend/src/app/report/[id]/page.tsx`

- Reads `id` from URL
- Calls `GET /api/v1/reports/{id}`
- Renders exact saved report

This is why every result URL is unique and shareable.

## 9. Routing Sequence (End-to-End)

1. User opens `/upload`.
2. User submits file.
3. Frontend sends `POST /api/v1/upload/`.
4. Backend generates media uuid and ledger uuid.
5. Backend returns report JSON with `id`.
6. Frontend navigates to `/report/{id}`.
7. Report route fetches and renders that record.

## 10. Why This Routing Design Is Legit and Scalable

- Dynamic route per report enables deep linking.
- Report page can be refreshed directly because route contains identity.
- Backend route uses primary key lookup for deterministic retrieval.
- Frontend and backend route concerns are cleanly separated.
- Dashboard routes are independent from report routes, keeping concerns modular.

## 11. Code Snippets (Current Core Routing Calls)

### Dynamic navigation after upload

From `frontend/src/app/upload/page.tsx`:

- `router.push(`/report/${report.id}`)`

### Dynamic route parameter read

From `frontend/src/app/report/[id]/page.tsx`:

- `const { id } = useParams()`

### Backend report lookup route

From `backend/app/api/v1/endpoints/reports.py`:

- `@router.get("/{ledger_id}")`
- query by `VerificationRecord.id == ledger_id`

## 12. Extending Routing Safely

If you add new routes later, follow this pattern:

1. Add page file under `src/app/...` for UI route.
2. Add backend endpoint under `backend/app/api/v1/endpoints/...`.
3. Build request URL through `apiUrl(...)` helper.
4. Keep URL identity explicit for deep-linkable resources.
5. Return stable IDs from backend for dynamic routes.

## 13. Quick Routing Audit Checklist

- [ ] Every page route has one source file in `src/app`
- [ ] Dynamic pages validate route params before fetch
- [ ] API URLs are built only through `apiUrl`
- [ ] Backend router prefixes are versioned (`/api/v1/...`)
- [ ] Unique IDs are backend-generated, not frontend-generated
- [ ] Error states are visible on invalid/missing route IDs

---

If you want, the next step can be a Route Contract document that maps each frontend route to its exact backend dependencies and response fields in a single table for onboarding and QA.
