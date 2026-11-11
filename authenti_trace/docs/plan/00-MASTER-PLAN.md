# AuthentiTrace Master Plan

Goal: move from the current prototype to a production-grade media-authenticity system.
Scores below are out of 100 and exclude Docker, auth and rate limiting.

| Area | Start | Target |
|---|---|---|
| Problem | 82 | 95+ |
| Architecture | 60 | 90+ |
| Solution | 35 | 85+ |

A literal 100 on detection is not reachable: new generators keep appearing. A measured and maintained 85-90 is the goal.

## Rules of the plan
- Measure first, then build models. No training before the Phase 2 test set exists.
- Phases run in order. Phases 3 and 4 may overlap after Phase 2 exits.
- A phase ends only when every exit criterion has proof in `STATUS.md`.
- Tasks that need data, GPU, money or a product decision go to the user.

## Phases

| # | File | Weeks | Owner | Moves |
|---|---|---|---|---|
| 0 | `phase-0-stabilize.md` | 1 | Claude | clean base |
| 1 | `phase-1-problem.md` | 1-2 | User decides, Claude drafts | Problem 82 → 95 |
| 2 | `phase-2-evaluation.md` | 2-4 | User data, Claude harness | honest baseline |
| 3 | `phase-3-architecture.md` | 3-7 | Claude | Architecture 60 → 90 |
| 4 | `phase-4-detection.md` | 5-12 | Claude + user data/GPU | Solution 35 → 85 |
| 5 | `phase-5-product.md` | 9-13 | Claude + user design | product quality |
| 6 | `phase-6-operations.md` | 12-16, then ongoing | Claude + user review | keeps scores up |

## Expected scores by phase end

| End of | Problem | Architecture | Solution |
|---|---|---|---|
| Phase 0 | 82 | 62 | 35 |
| Phase 1 | 95 | 62 | 35 |
| Phase 2 | 95 | 65 | 40 (measured) |
| Phase 3 | 95 | 90 | 40 |
| Phase 4 | 95 | 90 | 80-85 |
| Phase 5-6 | 95 | 92 | 85-90 |

## Inputs needed from the user
1. Niche and buyer (Phase 1).
2. Real and fake media, licensed or collected (Phase 2).
3. GPU option: local, cloud credits, or none (Phase 4).
4. Acceptable false-approval and false-alarm rates (Phase 1).

## Risks
- No data: Phases 2 and 4 stop. Start collecting early.
- Targets set without a baseline. Set them after the Phase 2 baseline run.
- Moving goalposts as generators improve. Phase 6 monthly refresh handles this.
- GPU cost for fine-tuning.
- Python 3.14 locally vs 3.12 target: check library wheels before adding ML packages.

## How to execute
The user says "start phase N". Claude reads the phase file, makes a branch `phase-N-<name>`, works tasks in order, updates `STATUS.md` with proof, and reports. No commits or pushes without a request.
