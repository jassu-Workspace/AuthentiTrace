from app.signals.base import ISignalPlugin
from app.signals.registry import registries
from app.schemas.verification import SignalResult


class IntegritySignal(ISignalPlugin):
    """Checks the file's SHA-256 against the known-malicious registry (registry/malicious_sha256.txt).

    The upload step hashes the bytes it just wrote, so re-hashing the file here could never differ.
    With an empty registry there is nothing to check, so the signal carries no weight.
    """

    @property
    def name(self) -> str:
        return "IntegritySignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        if file_hash.lower() in registries.malicious_sha256:
            return SignalResult(
                plugin_name=self.name,
                score=0.0,
                confidence=1.0,
                reasoning="Hash found in known malicious / explicit deepfake registry.",
                metadata={"file_hash": file_hash, "blacklist_hit": True, "registry_loaded": True},
            )

        if not registries.malicious_sha256:
            return SignalResult(
                plugin_name=self.name,
                score=50.0,
                confidence=0.0,
                reasoning="No malicious-hash registry is loaded, so this check carries no evidence.",
                metadata={"file_hash": file_hash, "blacklist_hit": False, "registry_loaded": False},
            )

        return SignalResult(
            plugin_name=self.name,
            score=100.0,
            confidence=0.6,  # a miss only means "not already known"; uncalibrated
            reasoning="File hash is not in the known malicious registry.",
            metadata={"file_hash": file_hash, "blacklist_hit": False, "registry_loaded": True},
        )
