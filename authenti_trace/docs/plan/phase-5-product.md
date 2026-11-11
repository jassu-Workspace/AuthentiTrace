# Phase 5 — Product and frontend (weeks 9-13)

Goal: users can trust and understand results. Owner: Claude, with user design choices. Branch: `phase-5-product`. Depends on Phase 3 (jobs API) and Phase 4 (UNSURE).

## Tasks
- [x] 5.1 Upload page: job status (queued, running, done, failed) using `GET /jobs/{id}`. Replace the spinner.
- [x] 5.2 Report page: per-signal plain-language explanation, confidence, and an UNSURE state with next steps.
- [x] 5.3 Human review queue: list of UNSURE items, reviewer decision stored as a ledger row.
- [x] 5.4 Verify page: input a ledger ID or file hash, show the chain proof and anchor status.
- [x] 5.5 Dashboard: accuracy on the latest labeled sample, review backlog, score distribution, drift indicator.
- [x] 5.6 Error, empty and offline states on every page. No raw server text.
- [~] 5.7 (labels, focus, live regions, contrast tokens and `aria-*` done and linted; no formal WCAG audit or screen-reader pass run) Accessibility review against WCAG 2.1 AA.
- [x] 5.8 Update TypeScript types to match `schemas/verification.py`.

## Done notes
- Walked through with the real backend: upload (job polling) -> report -> review decision -> verify -> dashboard. Upload driven by injecting a file into the input; native file picker not clicked.
- Review decisions store the reviewer name typed by the user until login exists (Phase 6).

## Exit criteria
- `npm run lint` and `npm run build` clean.
- Manual walkthrough of upload → job → report → review → verify recorded with screenshots.
- Accessibility review issues fixed.
