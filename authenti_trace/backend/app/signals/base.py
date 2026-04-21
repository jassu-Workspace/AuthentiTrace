from abc import ABC, abstractmethod
from app.schemas.verification import SignalResult

class ISignalPlugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the signal plugin"""
        pass

    @abstractmethod
    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        """Perform analysis and return a SignalResult with a score from 0-100"""
        pass
