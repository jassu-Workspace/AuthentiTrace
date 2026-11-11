"""Threat registries loaded from plain text files. Empty registry = no evidence, never "clean".

Files in REGISTRY_DIR (default backend/registry), one value per line, '#' starts a comment:
  malicious_sha256.txt   exact SHA-256 of files known to be malicious or synthetic
  synthetic_dhash.txt    64-bit dHash (16 hex chars) of known synthetic images
Call reload() after changing the files.
"""
import os
from pathlib import Path
from typing import Set

from app.database.database import BACKEND_DIR

REGISTRY_DIR = Path(os.getenv("REGISTRY_DIR", str(BACKEND_DIR / "registry")))
MAX_HAMMING_DISTANCE = int(os.getenv("DHASH_MAX_DISTANCE", "4"))  # of 64 bits; uncalibrated, tune with eval data


def _load(name: str) -> Set[str]:
    path = REGISTRY_DIR / name
    if not path.exists():
        return set()
    values = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.split("#", 1)[0].strip().lower()
        if value:
            values.add(value)
    return values


class Registries:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.malicious_sha256: Set[str] = _load("malicious_sha256.txt")
        self.synthetic_dhash: Set[str] = _load("synthetic_dhash.txt")

    def nearest_dhash_distance(self, dhash_hex: str) -> int | None:
        """Smallest Hamming distance to any registered dHash, or None when the registry is empty."""
        if not self.synthetic_dhash:
            return None
        value = int(dhash_hex, 16)
        return min(bin(value ^ int(known, 16)).count("1") for known in self.synthetic_dhash)


registries = Registries()
