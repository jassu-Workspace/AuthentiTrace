"""Trained image detector, run with ONNX Runtime. Registered only when IMAGE_MODEL_PATH is set.

Model file: any ONNX classifier taking one image and returning two logits or probabilities.
Sidecar `<model>.json` describes how to feed it:
  {"version": "my-model-2026-01", "input_size": [224, 224], "mean": [0.485, 0.456, 0.406],
   "std": [0.229, 0.224, 0.225], "real_index": 0, "confidence": 0.7}
`confidence` is how much weight the signal gets. Measure it on the validation split (backend/eval) and set it
there; until then keep it modest. Install onnxruntime (requirements-ml.txt).
"""
import hashlib
import json
import os
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from app.schemas.verification import SignalResult
from app.signals.base import ISignalPlugin


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


class OnnxImageDetector(ISignalPlugin):
    def __init__(self, model_path: str, sidecar_path: Optional[str] = None):
        import onnxruntime as ort  # imported here so installs without ML packages still run

        self.model_path = model_path
        with open(sidecar_path or os.path.splitext(model_path)[0] + ".json", encoding="utf-8") as f:
            self.cfg: Dict[str, Any] = json.load(f)
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        with open(model_path, "rb") as f:
            self.model_hash = hashlib.sha256(f.read()).hexdigest()

    @property
    def name(self) -> str:
        return "ModelSignal"

    @property
    def version(self) -> str:
        return f"{self.cfg.get('version', 'unversioned')}@{self.model_hash[:12]}"

    def _predict_real(self, media_path: str) -> float:
        width, height = self.cfg.get("input_size", [224, 224])
        with Image.open(media_path) as img:
            arr = np.asarray(img.convert("RGB").resize((width, height), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
        arr = (arr - np.array(self.cfg.get("mean", [0, 0, 0]), dtype=np.float32)) / np.array(
            self.cfg.get("std", [1, 1, 1]), dtype=np.float32
        )
        batch = np.transpose(arr, (2, 0, 1))[None].astype(np.float32)  # NCHW
        out = np.asarray(self.session.run(None, {self.input_name: batch})[0]).reshape(-1)
        probs = out if (out.min() >= 0 and abs(out.sum() - 1.0) < 1e-3) else _softmax(out)
        return float(probs[int(self.cfg.get("real_index", 0))])

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        try:
            p_real = self._predict_real(media_path)
        except Exception as exc:  # not an image, corrupt file, or a model/input mismatch
            return SignalResult(
                plugin_name=self.name, score=50.0, confidence=0.0,
                reasoning="The trained detector could not read this file, so it carries no evidence.",
                metadata={"error": type(exc).__name__, "model_version": self.version},
            )
        return SignalResult(
            plugin_name=self.name,
            score=round(p_real * 100.0, 2),
            confidence=float(self.cfg.get("confidence", 0.6)),
            reasoning=f"Trained detector estimates {p_real:.0%} probability the image is real.",
            metadata={"p_real": round(p_real, 4), "model_version": self.version},
        )


def load_configured_detector() -> Optional[OnnxImageDetector]:
    path = os.getenv("IMAGE_MODEL_PATH", "")
    return OnnxImageDetector(path) if path else None
