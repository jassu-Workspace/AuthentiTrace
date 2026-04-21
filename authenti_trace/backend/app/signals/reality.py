from app.signals.base import ISignalPlugin
from app.schemas.verification import SignalResult

class RealitySignal(ISignalPlugin):
    @property
    def name(self) -> str:
        return "RealitySignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        # Simulates checking EXIF data, C2PA signatures, and contextual metadata.
        # In a real system we would use tools like `exiftool` or a C2PA validator.
        deterministic_val = int(file_hash[8:12], 16) if len(file_hash) >= 12 else 0
        has_c2pa = (deterministic_val % 10) > 7  # 20% chance to have valid C2PA in this mock
        
        if has_c2pa:
            score = 100.0
            confidence = 0.99
            reason = "Valid C2PA provenance cryptographic signature verified. Origin confirmed."
            metadata = {"c2pa_present": True, "signer": "Verified Camera Vendor"}
        else:
            score = 40.0
            confidence = 0.70
            reason = "No C2PA data found. EXIF metadata appears stripped or generic."
            metadata = {"c2pa_present": False, "exif_stripped": True}

        return SignalResult(
            plugin_name=self.name,
            score=score,
            confidence=confidence,
            reasoning=reason,
            metadata=metadata
        )
