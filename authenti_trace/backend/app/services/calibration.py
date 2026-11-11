"""Turns the raw fused score into a measured probability, and loads learned fusion weights.

Both come from files written by the eval tools after a labeled run (backend/eval/fit_calibration.py,
backend/eval/fit_fusion.py). Without the files nothing changes: the raw score is used and reported as
"uncalibrated". Set CALIBRATION_PATH / FUSION_PATH to use other locations.
"""
import json
import math
import os
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from app.database.database import BACKEND_DIR

CALIBRATION_PATH = os.getenv("CALIBRATION_PATH", str(BACKEND_DIR / "calibration.json"))
FUSION_PATH = os.getenv("FUSION_PATH", str(BACKEND_DIR / "fusion.json"))


def _read(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_calibration(path: Optional[str] = None) -> Optional[dict]:
    """{"type": "platt", "a": float, "b": float, "version": str} or None."""
    data = _read(path or CALIBRATION_PATH)
    return data if data and data.get("type") == "platt" else None


def load_fusion_weights(path: Optional[str] = None) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
    data = _read(path or FUSION_PATH)
    if not data or not isinstance(data.get("weights"), dict):
        return None, None
    return {str(k): float(v) for k, v in data["weights"].items()}, str(data.get("version", "unversioned"))


def apply_platt(score: float, calibration: dict) -> float:
    """Raw score (0-100) -> probability the media is real, as a score (0-100)."""
    z = calibration["a"] * (score / 100.0) + calibration["b"]
    return round(100.0 / (1.0 + math.exp(-max(min(z, 60.0), -60.0))), 2)


def fit_platt(scores: Iterable[float], labels_real: Iterable[int], iterations: int = 50) -> Tuple[float, float]:
    """Fit p(real) = sigmoid(a * score/100 + b) by Newton's method with a small ridge term.

    Returns (a, b). Needs both classes present.
    """
    x = np.asarray(list(scores), dtype=float) / 100.0
    y = np.asarray(list(labels_real), dtype=float)
    if len(x) == 0 or y.min() == y.max():
        raise ValueError("calibration needs examples of both real and fake files")
    X = np.column_stack([x, np.ones_like(x)])
    w = np.zeros(2)
    ridge = 1e-6 * np.eye(2)
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -60, 60)))
        grad = X.T @ (p - y)
        hess = (X.T * (p * (1 - p))) @ X + ridge
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.abs(step).max() < 1e-9:
            break
    return float(w[0]), float(w[1])


def fit_fusion_weights(
    signals: List[Dict[str, Dict[str, float]]], labels_real: List[int], l2: float = 1.0, iterations: int = 100
) -> Dict[str, float]:
    """Learn one weight per signal from labeled results (rows of {name: {score, confidence}}).

    Feature per signal: confidence * (score - 50) / 50, so a silent signal (confidence 0) contributes nothing.
    A ridge-regularised logistic regression is fitted; weights are clipped to a small positive floor and
    rescaled to mean 1, so they plug into the existing confidence-weighted average.
    """
    names = sorted({n for row in signals for n in row})
    if not names or len(set(labels_real)) < 2:
        raise ValueError("fusion needs examples of both real and fake files")
    X = np.array([[row.get(n, {}).get("confidence", 0.0) * (row.get(n, {}).get("score", 50.0) - 50.0) / 50.0
                   for n in names] for row in signals])
    X = np.column_stack([X, np.ones(len(X))])
    y = np.asarray(labels_real, dtype=float)
    w = np.zeros(X.shape[1])
    reg = l2 * np.eye(X.shape[1])
    reg[-1, -1] = 0.0  # do not penalise the bias
    for _ in range(iterations):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -60, 60)))
        grad = X.T @ (p - y) + reg @ w
        hess = (X.T * (p * (1 - p))) @ X + reg + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.abs(step).max() < 1e-9:
            break
    raw = np.clip(w[:-1], 0.05, None)
    scaled = raw / raw.mean()
    return {n: round(float(v), 4) for n, v in zip(names, scaled)}
