import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.schemas.verification import SignalResult, ReportResponse
from app.services.scoring_engine import calculate_trust_score
from app.services.ledger_service import commit_verification

# Pluggable Signals
from app.signals.base import ISignalPlugin
from app.signals.content import ContentSignal
from app.signals.reality import RealitySignal
from app.signals.behavioral import BehavioralSignal
from app.signals.network import NetworkSignal
from app.signals.integrity import IntegritySignal

# Active plugins
PLUGINS: List[ISignalPlugin] = [
    ContentSignal(),
    RealitySignal(),
    BehavioralSignal(),
    NetworkSignal(),
    IntegritySignal()
]

# Static weights for demonstration (Can be fetched dynamically from DB in Prod)
SIGNAL_WEIGHTS = {
    "ContentSignal": 1.5,
    "RealitySignal": 1.0,
    "BehavioralSignal": 1.2,
    "NetworkSignal": 0.8,
    "IntegritySignal": 1.3
}

async def process_verification(db: AsyncSession, media_id: str, file_path: str, file_hash: str) -> ReportResponse:
    """Orchestrates the verification process across all independent signals and scores it."""
    
    # Run all signal plugins concurrently
    tasks = [plugin.analyze(media_path=file_path, file_hash=file_hash) for plugin in PLUGINS]
    gathered_results = await asyncio.gather(*tasks, return_exceptions=True)

    signal_results: List[SignalResult] = []
    for plugin, result in zip(PLUGINS, gathered_results):
        if isinstance(result, Exception):
            signal_results.append(
                SignalResult(
                    plugin_name=plugin.name,
                    score=0.0,
                    confidence=1.0,
                    reasoning=f"Signal execution failed: {type(result).__name__}",
                    metadata={"error": str(result)}
                )
            )
        else:
            signal_results.append(result)
    
    # Compile telemetry JSON directly from models
    telemetry: Dict[str, Any] = {
        result.plugin_name: result.model_dump()
        for result in signal_results
    }
    
    # Calculate weighted trust score
    scoring_result = calculate_trust_score(signal_results, SIGNAL_WEIGHTS)
    
    # Commit to Tamper-Evident Ledger
    ledger_record = await commit_verification(
        db=db,
        media_id=media_id,
        file_hash=file_hash,
        score=scoring_result.trust_score,
        risk=scoring_result.risk_category,
        action=scoring_result.enforcement_action,
        telemetry=telemetry
    )
    
    # Return Explainability Report JSON Wrapper
    return ReportResponse.model_validate(ledger_record)
