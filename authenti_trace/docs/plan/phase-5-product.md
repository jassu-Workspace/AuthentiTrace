# Phase 5 — Product and frontend (weeks 9-13)

Goal: users can trust and understand results. Owner: Claude, with user design choices. Branch: `phase-5-product`. Depends on Phase 3 (jobs API) and Phase 4 (UNSURE).

## Tasks
- [ ] 5.1 Upload page: job status (queued, running, done, failed) using `GET /jobs/{id}`. Replace the spinner.
- [ ] 5.2 Report page: per-signal plain-language explanation, confidence, and an UNSURE state with next steps.
- [ ] 5.3 Human review queue: list of UNSURE items, reviewer decision stored as a ledger row.
- [ ] 5.4 Verify page: input a ledger ID or file hash, show the chain proof and anchor status.
- [ ] 5.5 Dashboard: accuracy on the latest labeled sample, review backlog, score distribution, drift indicator.
- [ ] 5.6 Error, empty and offline states on every page. No raw server text.
- [ ] 5.7 Accessibility review against WCAG 2.1 AA.
- [ ] 5.8 Update TypeScript types to match `schemas/verification.py`.

## Exit criteria
- `npm run lint` and `npm run build` clean.
- Manual walkthrough of upload → job → report → review → verify recorded with screenshots.
- Accessibility review issues fixed.
