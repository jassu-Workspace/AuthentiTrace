# Baseline (Phase 2) — BLOCKED: no labeled data yet

The harness is built and tested, but no baseline number exists. Inventing one would be false.

## To produce the baseline
1. Add labeled real and fake media under `backend/eval/data/` and write `manifest.csv` (see `backend/eval/README.md`).
2. `python -m eval.make_splits eval/data/manifest.csv --seed 1337` (locks the test set).
3. `python -m eval.run_eval --manifest eval/data/manifest.csv --split val --out eval/results/baseline-val.json`
4. Paste the summary table here. Then write `eval/thresholds.json` from it and set the Phase 1 metric targets.

## Results
| Metric | Value |
|---|---|
| False-approval rate | not measured |
| False-alarm rate | not measured |
| Unsure rate | not measured |
| Calibration gap | not measured |
| Latency p95 | not measured |

The 25 files in `backend/storage/` are unlabeled uploads from manual testing. They cannot serve as a baseline.
