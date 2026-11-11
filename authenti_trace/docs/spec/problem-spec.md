# Problem spec (DRAFT — needs user approval)

Status: **provisional.** Claude chose the niche below as a default so Phases 2-3 are not blocked. The user must confirm or replace it (task 1.1). Competitor facts are **not verified** yet (task 1.4 research pending).

## 1. Niche and buyer (provisional default)

**Niche:** claim and listing photos — still images submitted as evidence in a workflow (insurance claims, marketplace listings, KYC document photos).
**Buyer:** a claims or trust-and-safety team that today checks photos by eye.
**Why this default:**
- Still images only: the current code and heuristics are strongest here. Video and audio come later.
- A missed fake has a clear cost (a paid false claim). A false alarm has a clear cost (a reviewer's time).
- Submitters often send phone photos with metadata intact, so provenance and tamper checks carry real signal.
- A reviewer queue already exists in these teams, so an `UNSURE` outcome fits their workflow.

**Alternatives the user may prefer:** newsroom photo verification (higher reputational cost, more re-compressed social images), KYC selfies (needs liveness, a different product).

## 2. Workflow

1. Submitter uploads a photo into the buyer's system.
2. The buyer's system calls AuthentiTrace with the file.
3. AuthentiTrace returns a verdict: `APPROVE`, `FLAG`, `RESTRICT`, or `MANUAL_REVIEW` (unsure), with per-signal reasons.
4. `APPROVE` passes automatically. `FLAG` and `MANUAL_REVIEW` go to a human. `RESTRICT` blocks or escalates.
5. Every verdict is written to the ledger. A reviewer or auditor can later prove what was said and when.

## 3. Cost of errors (to be filled with buyer numbers)

| Error | Meaning | Cost driver |
|---|---|---|
| False approval | A fake photo is approved | Paid fraudulent claim, reputation |
| False alarm | A real photo is flagged | Reviewer minutes, annoyed customer |
| Unsure | System abstains | Reviewer minutes |

Rule: the system may abstain, but it must never approve by default.

## 4. Volume and latency (assumptions, replace with buyer data)

- 1,000 to 50,000 photos per day.
- Target: verdict within 30 seconds for a 10 MB photo; results delivered by job polling or webhook.

## 5. Metrics (locked after the Phase 2 baseline)

| Metric | Definition | Target |
|---|---|---|
| False-approval rate | fake files that get `APPROVE` / all fake files | set from baseline; start with "below the baseline, then below 5%" |
| False-alarm rate | real files that get `FLAG` or `RESTRICT` / all real files | set from baseline |
| Unsure rate | files that get `MANUAL_REVIEW` / all files | set with the buyer's reviewer capacity |
| Calibration error | gap between stated score and measured share real | under 5 points per bin |
| Latency p95 | upload to verdict | under 30 s |
| Chain integrity | `/audit` clean, truncation detected | always |

No number is invented here. Phase 2 measures the baseline, then these targets are fixed with the user.

## 6. Scope

**In (first release):** still images (JPEG, PNG, WebP), verdict plus reasons, ledger and audit, reviewer queue.
**Next:** short video, then audio.
**Out:** live video streams, face identity matching, legal-grade forensic certification, takedown workflows.

## 7. Competitive edge (hypothesis, unverified)

Many detectors return a score with no record. AuthentiTrace's claimed edge is the pairing: a verdict plus a tamper-evident ledger a third party can audit, and an explicit `UNSURE` outcome. To verify: C2PA tooling, commercial deepfake-detection vendors, and open-source detectors. Research is pending (task 1.4).

## 8. Open decisions for the user
1. Approve or change the niche and buyer.
2. Supply buyer numbers for cost of errors and daily volume, or accept the assumptions.
3. Confirm scope order (images, then video, then audio).
