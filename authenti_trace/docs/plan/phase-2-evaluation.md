# Phase 2 — Evaluation first (weeks 2-4)

Goal: measure the solution before changing it. Owner: user supplies data, Claude builds tooling. Branch: `phase-2-eval`.

## Tasks
- [ ] 2.1 (BLOCKED: needs user data) User collects or licenses real media from the chosen niche and fakes from several generators and edit tools. Target: a few thousand samples. Include re-compressed, screenshot and resized copies.
- [x] 2.2 Define the dataset layout in `backend/eval/data/` (git-ignored): `real/`, `fake/<generator>/`, plus `manifest.csv` (path, label, source, generator, transform, split).
- [x] 2.3 Split: train, validation, locked test. The test split is never used for tuning. Record the split seed.
- [x] 2.4 Build `backend/eval/run_eval.py`: runs every signal and the full pipeline over a split. No database writes.
- [x] 2.5 Metrics: false-approval rate, false-alarm rate, UNSURE rate, per-media-type and per-generator accuracy, calibration curve, latency percentiles.
- [ ] 2.6 (BLOCKED: needs data) Run the current heuristics as baseline. Save to `backend/eval/results/baseline.json` and `docs/plan/baseline.md`.
- [x] 2.7 (partial) `run_eval --thresholds` exits 1 on regression. No CI workflow and no `thresholds.json` yet: both need the baseline.
- [ ] 2.8 (BLOCKED: needs baseline) Lock Phase 1 metric targets from the baseline.

## Exit criteria
- Baseline table published with real numbers.
- Locked test split exists and is hashed in `manifest.csv`.
- `python eval/run_eval.py --split val` runs in one command.

## Needs from the user
Data. Without it this phase stops. Claude must not generate fake training data by copying the heuristics' own outputs.
