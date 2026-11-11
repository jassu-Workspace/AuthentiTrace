"""Image transforms that mimic what happens to media in the wild (and what an attacker would try).

Each attack takes an input path and writes a new JPEG/PNG file. Used by run_attacks.py.
"""
import io
from pathlib import Path
from typing import Callable, Dict

import numpy as np
from PIL import Image, ImageFilter


def _open(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def _jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def jpeg_q50(img: Image.Image) -> Image.Image:
    return _jpeg(img, 50)


def jpeg_q30(img: Image.Image) -> Image.Image:
    return _jpeg(img, 30)


def resize_half(img: Image.Image) -> Image.Image:
    return img.resize((max(img.width // 2, 8), max(img.height // 2, 8)), Image.Resampling.LANCZOS)


def resize_down_up(img: Image.Image) -> Image.Image:
    small = img.resize((max(img.width // 2, 8), max(img.height // 2, 8)), Image.Resampling.BILINEAR)
    return small.resize(img.size, Image.Resampling.BILINEAR)


def crop_center_90(img: Image.Image) -> Image.Image:
    dx, dy = int(img.width * 0.05), int(img.height * 0.05)
    return img.crop((dx, dy, img.width - dx, img.height - dy))


def gaussian_noise(img: Image.Image) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32)
    noisy = arr + np.random.default_rng(0).normal(0, 6.0, arr.shape)
    return Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8))


def screenshot(img: Image.Image) -> Image.Image:
    """Resize, light blur, white border and a JPEG pass: what a phone screenshot of the image looks like."""
    shot = img.resize((int(img.width * 0.75), int(img.height * 0.75)), Image.Resampling.BILINEAR)
    shot = shot.filter(ImageFilter.GaussianBlur(0.6))
    framed = Image.new("RGB", (shot.width + 16, shot.height + 16), (255, 255, 255))
    framed.paste(shot, (8, 8))
    return _jpeg(framed, 85)


ATTACKS: Dict[str, Callable[[Image.Image], Image.Image]] = {
    "jpeg_q50": jpeg_q50,
    "jpeg_q30": jpeg_q30,
    "resize_half": resize_half,
    "resize_down_up": resize_down_up,
    "crop_center_90": crop_center_90,
    "gaussian_noise": gaussian_noise,
    "screenshot": screenshot,
}


def apply_attack(name: str, src: Path, dst: Path) -> Path:
    ATTACKS[name](_open(src)).save(dst, "PNG" if dst.suffix.lower() == ".png" else "JPEG", quality=95)
    return dst
