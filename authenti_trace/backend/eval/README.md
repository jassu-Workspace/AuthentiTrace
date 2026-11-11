# Evaluation harness (Phase 2)

Measures the pipeline on labeled media. No database writes.

1. Put media under `eval/data/` (git-ignored) and write `eval/data/manifest.csv`:
   `path,label,media_type,source,generator,transform` (`label` = `real` or `fake`; `path` relative to the manifest).
   Use one `source` per origin (camera, person, generator run) so near-duplicates stay in one split.
2. Assign splits and lock the test set: `python -m eval.make_splits eval/data/manifest.csv --seed 1337`
3. Evaluate: `python -m eval.run_eval --manifest eval/data/manifest.csv --split val --out eval/results/val.json`
4. Gate in CI: add `--thresholds eval/thresholds.json` (upper bounds, for example `{"false_approval_rate": 0.1}`).

Never tune on `test`. Report it once, at the end of a model change.
Do not fill the dataset with files produced by this repo's own heuristics: that measures nothing.
