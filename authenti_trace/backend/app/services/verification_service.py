"""
Verification Service Orchestrator
---------------------------------
Acts as the central architectural bridge across the AuthentiTrace subsystems:
1. Ingestion: Receives media ID, disk path, and hash from FastAPI endpoints.
2. Forensic Analysis: Concurrently evaluates media across independent, stateless ISignalPlugin instances.
   (Note: Signal plugins have no database dependency and do not access AsyncSession).
3. Trust Scoring: Aggregates signal telemetry through the confidence-aware scoring engine.
4. Tamper-Evident Ledger: Persists results into SQLite sequential hash chain via commit_verification(db, ...).
"""

import asyncio
import logging
import os
import time
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Tuple

from app import metrics
from app.schemas.verification import SignalResult, ScoringResult, ReportResponse
from app.services.calibration import load_calibration, load_fusion_weights
from app.services.scoring_engine import calculate_trust_score
from app.services.ledger_service import commit_verification

# Pluggable Signals (Stateless, independent of AsyncSession)
from app.signals.base import ISignalPlugin
from app.signals.heuristic_signals import ContentSignal, RealitySignal, BehavioralSignal, NetworkSignal
from app.signals.integrity import IntegritySignal
from app.signals.onnx_detector import load_configured_detector

logger = logging.getLogger(__name__)

# Active plugins
PLUGINS: List[ISignalPlugin] = [
    ContentSignal(),
    RealitySignal(),
    BehavioralSignal(),
    NetworkSignal(),
    IntegritySignal()
]

# Optional trained detector (IMAGE_MODEL_PATH). Its version and file hash go into every ledger row.
_detector = load_configured_detector()
if _detector:
    PLUGINS.append(_detector)

# Static weights for demonstration (Can be fetched dynamically from DB in Prod)
SIGNAL_WEIGHTS = {
    "ModelSignal": 2.0,
    "ContentSignal": 1.5,
    "RealitySignal": 1.0,
    "BehavioralSignal": 1.2,
    "NetworkSignal": 0.8,
    "IntegritySignal": 1.3
}

_fusion_weights, _fusion_version = load_fusion_weights()
if _fusion_weights:
    SIGNAL_WEIGHTS = {**SIGNAL_WEIGHTS, **_fusion_weights}  # learned on labeled data (eval/fit_fusion.py)
CALIBRATION = load_calibration()  # eval/fit_calibration.py; None means scores stay uncalibrated

# Recorded in every ledger row. Bump "pipeline" when signals, rules or thresholds change, so old rows can
# be told apart and re-scored (app/services/rescore.py). Fusion and calibration versions come from their files.
VERSIONS = {
    "pipeline": "4.0",
    "thresholds": "1",
    "model": _detector.version if _detector else "heuristic-1",
    "fusion": _fusion_version or "default",
    "calibration": (CALIBRATION or {}).get("version", "none"),
}

SIGNAL_TIMEOUT_SECONDS = float(os.getenv("SIGNAL_TIMEOUT_SECONDS", "60"))


async def _run_plugin(plugin: ISignalPlugin, file_path: str, file_hash: str) -> SignalResult:
    """Run one plugin in a worker thread so its CPU work cannot block the event loop.

    shortcut: a timed-out thread keeps running until it finishes (threads cannot be killed);
    move signals to separate worker processes (Celery) if that becomes a resource problem.
    """
    def call() -> SignalResult:
        return asyncio.run(plugin.analyze(media_path=file_path, file_hash=file_hash))

    started = time.perf_counter()
    try:
        return await asyncio.wait_for(asyncio.to_thread(call), timeout=SIGNAL_TIMEOUT_SECONDS)
    finally:
        metrics.observe("authentitrace_signal", time.perf_counter() - started, signal=plugin.name)


async def analyze_media(file_path: str, file_hash: str) -> Tuple[List[SignalResult], ScoringResult]:
    """Run every signal and score the result. No database access (also used by the eval harness)."""
    gathered_results = await asyncio.gather(
        *[_run_plugin(plugin, file_path, file_hash) for plugin in PLUGINS], return_exceptions=True
    )

    signal_results: List[SignalResult] = []
    for plugin, result in zip(PLUGINS, gathered_results):
        if isinstance(result, BaseException):
            # A failed or timed-out signal carries zero weight. Keep exception text out of the ledger and the API.
            logger.error("Signal %s failed", plugin.name, exc_info=result)
            signal_results.append(
                SignalResult(
                    plugin_name=plugin.name,
                    score=50.0,
                    confidence=0.0,
                    reasoning=f"Signal execution failed: {type(result).__name__}",
                    metadata={"error": type(result).__name__}
                )
            )
        else:
            signal_results.append(result)

    scoring = calculate_trust_score(signal_results, SIGNAL_WEIGHTS, CALIBRATION)
    metrics.inc("authentitrace_verdicts_total", action=scoring.enforcement_action)
    return signal_results, scoring


async def process_verification(db: AsyncSession, media_id: str, file_path: str, file_hash: str) -> ReportResponse:
    """
    Central pipeline orchestrator:
    - Runs the signals (analyze_media) and computes the confidence-weighted trust score.
    - Persists the outcome into the cryptographic ledger via commit_verification.
    - Returns serialized ReportResponse for frontend display.
    """
    signal_results, scoring_result = await analyze_media(file_path, file_hash)

    # Compile telemetry JSON directly from models
    telemetry: Dict[str, Any] = {
        result.plugin_name: result.model_dump()
        for result in signal_results
    }
    # Keys that start with "_" are not signals. Hashed with the row, so the decision is tamper-evident too.
    telemetry["_decision"] = {
        "reason": scoring_result.reason,
        "evidence": scoring_result.evidence,
        "calibrated": scoring_result.calibrated,
    }

    # Commit to Tamper-Evident Ledger
    ledger_record = await commit_verification(
        db=db,
        media_id=media_id,
        file_hash=file_hash,
        score=scoring_result.trust_score,
        risk=scoring_result.risk_category,
        action=scoring_result.enforcement_action,
        telemetry=telemetry,
        versions=VERSIONS,
    )
    
    # Return Explainability Report JSON Wrapper
    return ReportResponse.model_validate(ledger_record)
