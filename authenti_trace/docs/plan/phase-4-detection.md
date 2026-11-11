# Phase 4 — Detection upgrade (weeks 5-12)

Goal: Solution score 35 → 85. Owner: Claude builds, user supplies data and GPU. Branch: `phase-4-detection`. Requires Phase 2 exit.

Rule: keep a change only if it improves the Phase 2 validation numbers. Report the delta every time.

## Tasks
- [ ] 4.1 Provenance: real C2PA signature verification (replace byte sniffing in `RealitySignal`). Fill the registries (`KNOWN_MALICIOUS_HASHES`, synthetic dHash set) from real sources, or return `confidence=0` while they are empty.
- [ ] 4.2 Image detector: pick an open-source pretrained model, wrap it as an `ISignalPlugin`, export to ONNX if useful. Fine-tune on the train split. Compare to baseline.
- [ ] 4.3 Video detector: frame sampling plus a temporal model. Keep rPPG and cadence checks only if they help on validation.
- [ ] 4.4 Audio detector: pretrained voice-spoof model, fine-tuned.
- [ ] 4.5 Fusion: replace the weighted average in `scoring_engine.py` with a learned or calibrated combiner. Fit on validation, evaluate on the locked test split once.
- [ ] 4.6 Calibration: scores map to measured probability. Publish the calibration curve.
- [ ] 4.7 Abstain: add `UNSURE` risk category and `MANUAL_REVIEW` action. Trigger on low evidence or signal disagreement. Remove default-approve behavior (the 85-on-error and 95-always-clean paths).
- [ ] 4.8 Adversarial pass: screenshots, re-encoding, crops, noise, resizing. Record the accuracy drop per attack.
- [ ] 4.9 Version everything (Phase 3 task 3.13) and record model hashes.

## Exit criteria
- Locked test split meets the Phase 1 targets.
- Calibration curve and per-generator table published in `docs/plan/results.md`.
- No signal returns a positive score without evidence.
- Audit finding 6 closed.

## Needs from the user
GPU access, data, and the decision on acceptable error rates. Claude must stop and ask if a model needs a license review.
