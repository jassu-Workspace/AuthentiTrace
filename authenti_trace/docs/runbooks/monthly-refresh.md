# Runbook: monthly refresh

New media generators appear every month. A detector that was good last quarter can miss today's fakes. Run this every month.

1. **Collect.** Add new real files and fakes from the newest generators and tools to `backend/eval/data/` and `manifest.csv`. Include re-compressed and screenshot copies. Add confirmed missed fakes from incidents (see `missed-fake-incident.md`).
2. **Split.** `python -m eval.make_splits eval/data/manifest.csv --seed 1337`. Existing files keep their split. Changing the locked test set is refused on purpose.
3. **Measure the current system.** `python -m eval.run_eval --manifest eval/data/manifest.csv --split val --out eval/results/val.json`. Compare with last month's numbers. Run `python -m eval.run_attacks ...` too.
4. **Improve (only if numbers fell).** Retrain or swap the model, refit fusion (`eval.fit_fusion`) and calibration (`eval.fit_calibration`, run with `CALIBRATION_PATH=none`) on the validation split. Bump `VERSIONS["pipeline"]` in `verification_service.py` when rules or thresholds change.
5. **Gate.** Run `run_eval` with `--thresholds eval/thresholds.json`. Ship only if every limit holds. Update `thresholds.json` only to make it stricter.
6. **Report once on the test split.** `--split test --out eval/results/test-<date>.json`. Never tune on it.
7. **Publish the numbers.** Copy the validation summary to `backend/eval/results/latest.json` (the dashboard reads it) and add a dated row to `docs/plan/results.md`.
8. **Re-score old media if the pipeline changed.** `python -m app.services.rescore`. It adds new rows and never edits old ones.
9. **Check drift.** `python -m app.services.drift_check`. Exit code 1 means the recent score distribution moved a lot.

Record the date, the numbers and who ran it in `docs/plan/STATUS.md`.
