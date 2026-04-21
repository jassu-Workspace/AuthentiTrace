import os
from app.signals.base import ISignalPlugin
from app.schemas.verification import SignalResult

class BehavioralSignal(ISignalPlugin):
    @property
    def name(self) -> str:
        return "BehavioralSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        # Simulates eye-tracking, blink rate, and lip-sync variance.
        ext = os.path.splitext(media_path)[1].lower() if media_path else ""
        
        # If it's just an image, behavioral motion does not apply perfectly, or we analyze pose.
        if ext in ['.jpg', '.jpeg', '.png']:
            return SignalResult(
                plugin_name=self.name,
                score=85.0,
                confidence=0.6,
                reasoning="Static media. Limited behavioral analysis available; pose looks natural.",
                metadata={"motion_analyzed": False, "pose_estimation_variance": 0.12}
            )
            
        # For video/audio: simulate lip-sync and blink rate deterministically
        deterministic_val = int(file_hash[4:8], 16) if len(file_hash) >= 8 else 0
        sync_error = (deterministic_val % 100) / 100.0
        
        if sync_error > 0.8:
            score = 25.0
            confidence = 0.89
            reason = "Significant audio-visual desynchronization and unnatural blink frequency detected."
        else:
            score = 90.0
            confidence = 0.82
            reason = "Motion kinematics and audio-visual sync are within human baselines."
            
        return SignalResult(
            plugin_name=self.name,
            score=score,
            confidence=confidence,
            reasoning=reason,
            metadata={"sync_error_margin": sync_error, "motion_analyzed": True}
        )
