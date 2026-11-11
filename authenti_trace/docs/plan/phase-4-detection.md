# Phase 4 — Detection upgrade (weeks 5-12)

Goal: Solution score 35 → 85. Owner: Claude builds, user supplies data and GPU. Branch: `phase-4-detection`. Requires Phase 2 exit.

Rule: keep a change only if it improves the Phase 2 validation numbers. Report the delta every time.

## Tasks
- [~] 4.1 (code done: real C2PA via the c2pa library, forged markers no longer count, registry loaders. Positive path untested: no signed sample file. Registries are EMPTY: you must fill `backend/registry/`.) Provenance: real C2PA signature verification (replace byte sniffing in `RealitySignal`). Fill the registries (`KNOWN_MALICIOUS_HASHES`, synthetic dHash set) from real sources, or return `confidence=0` while they are empty.
- [~] 4.2 (plug-in ready: `ONNX` detector via `IMAGE_MODEL_PATH`, tested with a tiny model. The real model and fine-tuning need your data and GPU.) Image detector: pick an open-source pretrained model, wrap it as an `ISignalPlugin`, export to ONNX if useful. Fine-tune on the train split. Compare to baseline.
- [~] 4.3 (no video model yet; the pulse heuristic now gives no evidence unless a pulse is found.) Video detector: frame sampling plus a temporal model. Keep rPPG and cadence checks only if they help on validation.
- [~] 4.4 (no audio model yet; audio goes to MANUAL_REVIEW.) Audio detector: pretrained voice-spoof model, fine-tuned.
- [~] 4.5 (fitting tool `eval/fit_fusion.py` done and tested on synthetic data. Needs your labeled data to produce real weights.) Fusion: replace the weighted average in `scoring_engine.py` with a learned or calibrated combiner. Fit on validation, evaluate on the locked test split once.
- [~] 4.6 (`eval/fit_calibration.py` and score mapping done. Needs your labeled data.) Calibration: scores map to measured probability. Publish the calibration curve.
- [x] 4.7 (UNKNOWN / MANUAL_REVIEW on too little evidence or strong disagreement; empty registries and failed signals carry zero weight. Limits are uncalibrated placeholders.) Abstain: add `UNSURE` risk category and `MANUAL_REVIEW` action. Trigger on low evidence or signal disagreement. Remove default-approve behavior (the 85-on-error and 95-always-clean paths).
- [~] 4.8 (`eval/run_attacks.py` with 7 attacks done and tested on synthetic images. Running it for real needs your data.) Adversarial pass: screenshots, re-encoding, crops, noise, resizing. Record the accuracy drop per attack.
- [x] 4.9 (`versions` records pipeline, thresholds, model name + file hash, fusion and calibration versions.) Version everything (Phase 3 task 3.13) and record model hashes.

## Exit criteria
- Locked test split meets the Phase 1 targets.
- Calibration curve and per-generator table published in `docs/plan/results.md`.
- No signal returns a positive score without evidence.
- Audit finding 6 closed.

## Needs from the user
GPU access, data, and the decision on acceptable error rates. Claude must stop and ask if a model needs a license review.
