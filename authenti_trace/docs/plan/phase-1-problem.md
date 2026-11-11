# Phase 1 — Sharpen the problem (weeks 1-2)

Goal: Problem score 82 → 95. Owner: user decides, Claude drafts. Branch: `phase-1-spec`.

## Tasks
- [ ] 1.1 User picks one niche and one buyer. Candidates: newsroom photo verification, insurance claim photos, KYC selfies, marketplace listing photos.
- [ ] 1.2 Claude drafts `docs/spec/problem-spec.md`: buyer, workflow, cost of a missed fake, cost of a false alarm, volume per day.
- [ ] 1.3 Define media scope order: still images first, then short video, then audio.
- [ ] 1.4 Claude researches 2-3 competitors (C2PA tooling, Reality Defender, Hive) and writes the one-line advantage.
- [ ] 1.5 Set metric targets after the Phase 2 baseline: false-approval rate, false-alarm rate, UNSURE rate, latency per file.
- [ ] 1.6 List what is out of scope.

## Exit criteria
- `docs/spec/problem-spec.md` approved by the user.
- Metric targets written as numbers (placeholders allowed until Phase 2 baseline, then locked).
