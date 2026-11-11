# CLAUDE.md — frontend

Read the root `CLAUDE.md` first. This file covers `frontend/` only.

## Stack
Next.js 16.1.6 (App Router, `next dev --webpack`), React 19.2.3, TypeScript 5. Check `package.json` before assuming Tailwind or other libraries.

## Layout
- `src/app/page.tsx` — landing.
- `src/app/upload/page.tsx` — upload form, calls `POST /api/v1/upload/`.
- `src/app/report/[id]/page.tsx` — report view, calls `GET /api/v1/reports/{id}`.
- `src/app/dashboard/page.tsx` — metrics and audit, calls `/api/v1/dashboard/metrics` and `/audit`.
- `src/lib/api.ts` — `apiUrl()` and `API_BASE_URL` (env `NEXT_PUBLIC_API_URL`; dev default `http://127.0.0.1:8000`).

## Rules
- All backend calls go through `apiUrl()`. No hard-coded hosts.
- Types for API responses match `backend/app/schemas/verification.py`. Change both together.
- Handle loading, error, empty and "unsure" states on every page. Never show raw server error text.
- Do not render backend strings as HTML.
- Keep accessibility: labels, focus states, contrast (WCAG 2.1 AA).
- Run `npm run lint` and `npm run build` before claiming a task is done.

## Phase map for this folder
- Phase 0: confirm production API URL handling (empty `NEXT_PUBLIC_API_URL` in production calls a relative path).
- Phase 5: job status UI, plain-language explanations, UNSURE state, review queue, verify-by-hash page, accuracy dashboard.
