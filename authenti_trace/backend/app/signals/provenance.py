"""Content Credentials (C2PA) verification through the official c2pa library.

A byte pattern like "c2pa" proves nothing (anyone can write those bytes into a file). Only the library's
validation of the signed manifest counts as verified provenance.
"""
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Digital source types that declare AI generation (IPTC / C2PA vocabulary).
AI_SOURCE_MARKERS = ("trainedAlgorithmicMedia", "compositeWithTrainedAlgorithmicMedia", "algorithmicMedia")


def interpret_c2pa(state: str, manifest_text: str) -> Dict[str, Any]:
    """Turn the library's validation state and manifest JSON into the facts the signal needs. Pure function."""
    try:
        manifest = json.loads(manifest_text) if manifest_text else {}
    except ValueError:
        manifest = {}
    active = (manifest.get("manifests") or {}).get(manifest.get("active_manifest") or "", {})
    return {
        "state": state,  # "Valid", "Trusted" or "Invalid"
        "verified": state in ("Valid", "Trusted"),
        "trusted": state == "Trusted",
        "ai_generated": any(marker in manifest_text for marker in AI_SOURCE_MARKERS),
        "claim_generator": str(active.get("claim_generator") or "")[:120] or None,
    }


def read_c2pa(path: str) -> Optional[Dict[str, Any]]:
    """Return the verified facts, or None when the file has no manifest (or the library is unavailable)."""
    try:
        import c2pa
    except ImportError:
        return None
    try:
        with c2pa.Reader(path) as reader:
            return interpret_c2pa(reader.get_validation_state() or "Invalid", reader.json())
    except Exception as exc:  # no manifest, unsupported type, or a corrupt manifest
        if "ManifestNotFound" not in str(exc) and "NotSupported" not in str(exc):
            logger.warning("C2PA read failed: %s", type(exc).__name__)
        return None
