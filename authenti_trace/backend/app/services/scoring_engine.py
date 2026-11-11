import os
from typing import List, Dict, Optional

from app.schemas.verification import SignalResult, ScoringResult
from app.services.calibration import apply_platt

# Abstain (MANUAL_REVIEW) instead of guessing. Both limits are uncalibrated placeholders:
# tune them from the Phase 2 evaluation (backend/eval) before relying on them.
MIN_EFFECTIVE_WEIGHT = float(os.getenv("SCORING_MIN_EVIDENCE", "1.0"))  # total confidence-weighted evidence needed
MAX_DISAGREEMENT = float(os.getenv("SCORING_MAX_DISAGREEMENT", "50"))  # score spread allowed among confident signals
CONFIDENT = 0.5  # a signal counts as "confident" for the disagreement check at or above this


def _abstain(raw: float, reason: str, evidence: float, calibrated: bool) -> ScoringResult:
    return ScoringResult(
        trust_score=round(raw, 2), risk_category="UNKNOWN", enforcement_action="MANUAL_REVIEW",
        reason=reason, evidence=round(evidence, 3), calibrated=calibrated,
    )


def calculate_trust_score(
    signals: List[SignalResult], weights: Dict[str, float], calibration: Optional[dict] = None
) -> ScoringResult:
    """
    Combines independent signals into a trust score and an action.
    1. Confidence-weighted average (a silent signal, confidence 0, counts for nothing).
    2. A confident very-low signal is a critical failure and caps the score at 20.
    3. Too little evidence, or confident signals that disagree, gives UNKNOWN / MANUAL_REVIEW.
    4. If a calibration is supplied, the raw score is mapped to a measured probability first.
    """
    if not signals:
        return _abstain(0.0, "No signals were produced.", 0.0, False)

    total_weighted_score = 0.0
    total_effective_weight = 0.0
    critical_failure = False
    confident_scores: List[float] = []

    for signal in signals:
        normalized_score = min(max(float(signal.score), 0.0), 100.0)
        normalized_confidence = min(max(float(signal.confidence), 0.0), 1.0)
        effective_weight = weights.get(signal.plugin_name, 1.0) * normalized_confidence

        total_weighted_score += normalized_score * effective_weight
        total_effective_weight += effective_weight

        if normalized_score < 10.0 and normalized_confidence > 0.9:
            critical_failure = True
        if normalized_confidence >= CONFIDENT:
            confident_scores.append(normalized_score)

    if total_effective_weight == 0:
        return _abstain(0.0, "Every signal failed or had no evidence.", 0.0, False)

    raw_score = total_weighted_score / total_effective_weight
    if critical_failure:
        raw_score = min(raw_score, 20.0)  # a confirmed hit (known fake, broken credentials) outweighs the rest
    elif total_effective_weight < MIN_EFFECTIVE_WEIGHT:
        return _abstain(raw_score, "Not enough evidence to decide.", total_effective_weight, False)
    elif len(confident_scores) >= 2 and max(confident_scores) - min(confident_scores) > MAX_DISAGREEMENT:
        return _abstain(raw_score, "Signals disagree strongly; a person should look.", total_effective_weight, False)

    final_score = apply_platt(raw_score, calibration) if calibration else raw_score

    if final_score < 40:
        risk_category, enforcement_action = "HIGH_RISK", "RESTRICT"
    elif final_score < 75:
        risk_category, enforcement_action = "MEDIUM_RISK", "FLAG"
    else:
        risk_category, enforcement_action = "LOW_RISK", "APPROVE"

    return ScoringResult(
        trust_score=round(final_score, 2),
        risk_category=risk_category,
        enforcement_action=enforcement_action,
        reason="Critical failure from a confident signal." if critical_failure else "",
        evidence=round(total_effective_weight, 3),
        calibrated=bool(calibration),
    )
