import hashlib
import json
from typing import Dict, Any

def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA-256 for a raw file stream."""
    return hashlib.sha256(content).hexdigest()

def calculate_ledger_hash(previous_hash: str, payload: Dict[str, Any]) -> str:
    """Calculate the cryptographic hash for the ledger chain."""
    # Ensure stable sorting for deterministic hashing
    # separators=(',', ':') removes whitespace assuring canonical minified integrity
    payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    combined = f"{previous_hash}|{payload_str}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()
