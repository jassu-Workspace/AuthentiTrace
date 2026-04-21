from typing import List, Dict, Any
from app.schemas.verification import SignalResult, ScoringResult


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))

def calculate_trust_score(signals: List[SignalResult], weights: Dict[str, float]) -> ScoringResult:
    """
    Calculates weighted trust score from independent signals.
    Implements a robust scoring heuristic:
    1. Base weighted average
    2. Confidence intervals masking (low confidence signals impact score less)
    3. Critical failure penalization (if integrity is 0, score tanks)
    """
    if not signals:
        return ScoringResult(trust_score=0.0, risk_category="UNKNOWN", enforcement_action="MANUAL_REVIEW")

    total_weighted_score = 0.0
    total_effective_weight = 0.0
    
    # Track critical failures
    critical_failure = False

    for signal in signals:
        normalized_score = _clamp(float(signal.score), 0.0, 100.0)
        normalized_confidence = _clamp(float(signal.confidence), 0.0, 1.0)
        base_weight = weights.get(signal.plugin_name, 1.0)
        
        # Effective weight scales with the signal's confidence
        effective_weight = base_weight * normalized_confidence
        
        total_weighted_score += (normalized_score * effective_weight)
        total_effective_weight += effective_weight
        
        # Hard penalty rule: if a high-confidence Integrity or Content signal gives terrible score, fail it.
        if normalized_score < 10.0 and normalized_confidence > 0.9:
            critical_failure = True

    final_score = (total_weighted_score / total_effective_weight) if total_effective_weight > 0 else 0.0
    
    if critical_failure:
        # Cap score at 20 if there's a critical, high-confidence fail (like a compromised cryptographic hash)
        final_score = min(final_score, 20.0)

    # Automated Enforcement Logic Rules
    if final_score < 40:
        risk_category = "HIGH_RISK"
        enforcement_action = "RESTRICT"
    elif final_score < 75:
        risk_category = "MEDIUM_RISK"
        enforcement_action = "FLAG"
    else:
        risk_category = "LOW_RISK"
        enforcement_action = "APPROVE"

    return ScoringResult(
        trust_score=round(final_score, 2),
        risk_category=risk_category,
        enforcement_action=enforcement_action
    )
