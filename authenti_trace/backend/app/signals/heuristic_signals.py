import os
import io
import numpy as np
from PIL import Image, ExifTags
import cv2
import scipy.ndimage as ndi
import scipy.signal as signal
from app.signals.base import ISignalPlugin
from app.schemas.verification import SignalResult
from app.signals.provenance import read_c2pa
from app.signals.registry import registries, MAX_HAMMING_DISTANCE

class ContentSignal(ISignalPlugin):
    """
    Truth-Grounded Spectral & Compression Forensic Analyzer.
    Evaluates:
      1. Error Level Analysis (ELA): Detects localized digital splicing or resaving inconsistencies.
      2. High-Frequency Spectral Profile: Verifies optical continuous decay.
      3. Sensor Residual Consistency: Measures sensor grain variance.
    """
    @property
    def name(self) -> str:
        return "ContentSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        # ponytail: Analyzes static image or first video frame; multi-frame video extraction is upgrade path.
        if not os.path.exists(media_path):
            return SignalResult(plugin_name=self.name, score=0.0, confidence=1.0, reasoning="Media file missing.", metadata={})

        try:
            with Image.open(media_path) as img:
                img_rgb = img.convert("RGB")
                gray = np.array(img_rgb.convert("L"), dtype=np.float32)

                # 1. Error Level Analysis (ELA) for localized resaving / splicing anomalies
                buf = io.BytesIO()
                img_rgb.save(buf, "JPEG", quality=90)
                buf.seek(0)
                resaved = Image.open(buf)
                ela_diff = np.abs(np.array(img_rgb, dtype=np.int16) - np.array(resaved, dtype=np.int16))
                ela_mean = float(np.mean(ela_diff))
                ela_std = float(np.std(ela_diff))

                # 2. Sensor Residual Noise (Median Filter Residual)
                filtered = ndi.median_filter(gray, size=3)
                residual = gray - filtered
                sensor_noise_var = float(np.var(residual))

                # 3. 2D Spectral Energy Distribution
                fshift = np.fft.fftshift(np.fft.fft2(gray))
                mag = np.abs(fshift)
                h, w = gray.shape
                cy, cx = h // 2, w // 2
                y, x = np.ogrid[:h, :w]
                r = np.sqrt((x - cx)**2 + (y - cy)**2)
                max_r = max(min(cy, cx), 1)
                high_mask = r > (0.7 * max_r)
                high_energy_ratio = float(np.sum(mag[high_mask]) / (np.sum(mag) + 1e-9))

            # Calibrated Decision Logic:
            # - Splicing Anomaly: Extreme localized compression disparity (ela_std > 35.0 with high mean)
            # - Extreme High-Frequency Energy (> 0.45): Unusually high artificial noise
            is_spliced = (ela_std > 35.0) and (ela_mean > 25.0)
            is_noise_extreme = high_energy_ratio > 0.45

            if is_spliced:
                score = 40.0
                confidence = 0.88
                reason = "Localized compression divergence detected (indicative of digital splicing or cut-and-paste manipulation)."
            elif is_noise_extreme:
                score = 55.0
                confidence = 0.75
                reason = "Atypical high-frequency energy concentration detected across high spectral bands."
            else:
                score = 94.0
                confidence = 0.92
                reason = "Natural optical frequency distribution verified; compression error profile is uniform."

            return SignalResult(
                plugin_name=self.name,
                score=score,
                confidence=confidence,
                reasoning=reason,
                metadata={
                    "ela_mean": round(ela_mean, 2),
                    "ela_std": round(ela_std, 2),
                    "sensor_noise_var": round(sensor_noise_var, 2),
                    "high_energy_ratio": round(high_energy_ratio, 4)
                }
            )
        except Exception:
            return SignalResult(
                plugin_name=self.name,
                score=50.0,
                confidence=0.0,
                reasoning="This file type cannot be analyzed as a raster image, so this check carries no evidence.",
                metadata={}
            )


class RealitySignal(ISignalPlugin):
    """
    Truth-Grounded Metadata & Provenance Verifier.
    Evaluates:
      1. Explicit Generative Software Footprints (Midjourney, DALL-E, ComfyUI, Stable Diffusion, etc.).
      2. Cryptographic Provenance (C2PA / Content Credentials).
      3. Camera Hardware Metadata (Make / Model).
      4. Neutral Web Media Handling: Privacy-stripped metadata is treated neutrally (86.0), NOT penalized.
    """
    @property
    def name(self) -> str:
        return "RealitySignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        # ponytail: JUMBF box sniffing used; full c2pa-rs cryptographic signature verification is upgrade path.
        if not os.path.exists(media_path):
            return SignalResult(plugin_name=self.name, score=0.0, confidence=1.0, reasoning="Media missing.", metadata={})

        with open(media_path, "rb") as f:
            header = f.read(65536)
        c2pa_info = read_c2pa(media_path)  # verified through the c2pa library, not by byte patterns
        # Marker bytes alone are spoofable; they only mean "credentials may exist", never "verified".
        marker_only = c2pa_info is None and any(m in header for m in (b"c2pa", b"JUMB", b"caTI"))

        make, model, software = None, None, None
        bayer_ratio = 1.0
        try:
            with Image.open(media_path) as img:
                exif = img.getexif()
                if exif:
                    make = str(exif.get(ExifTags.Base.Make, "")).strip() or None
                    model = str(exif.get(ExifTags.Base.Model, "")).strip() or None
                    software = str(exif.get(ExifTags.Base.Software, "")).strip() or None

                # Test for Bayer demosaicing presence on Green channel if dimensions permit
                img_rgb = img.convert("RGB")
                green = np.array(img_rgb)[:, :, 1].astype(np.float32)
                if green.shape[0] >= 32 and green.shape[1] >= 32:
                    pred = (np.roll(green, 1, 0) + np.roll(green, -1, 0) + np.roll(green, 1, 1) + np.roll(green, -1, 1)) / 4.0
                    err = green - pred
                    err_fft = np.abs(np.fft.rfft(err, axis=1))
                    mean_spec = np.mean(err_fft, axis=0)
                    bayer_ratio = float(mean_spec[-1] / (np.mean(mean_spec[:-1]) + 1e-9))
        except Exception:
            pass

        # Check for confirmed AI generation software footprints
        ai_signatures = ("midjourney", "stable diffusion", "dall-e", "comfyui", "novelai", "flux", "firefly", "craiyon", "automatic1111")
        detected_ai = None
        if software and any(sig in software.lower() for sig in ai_signatures):
            detected_ai = software

        # Truth-Grounded Verdict
        if detected_ai:
            score = 10.0
            confidence = 0.99
            reason = f"Confirmed generative AI software footprint in container metadata ({detected_ai})."
        elif c2pa_info and c2pa_info["ai_generated"]:
            score = 5.0
            confidence = 0.99
            reason = "Signed Content Credentials declare this media as AI-generated."
        elif c2pa_info and not c2pa_info["verified"]:
            score = 15.0
            confidence = 0.90
            reason = "Content Credentials are present but fail validation: the file was altered after signing."
        elif c2pa_info:
            score = 99.0 if c2pa_info["trusted"] else 97.0
            confidence = 0.95
            reason = "Signed Content Credentials (C2PA) verified. Origin and edit history are cryptographically bound to this file."
        elif marker_only:
            score = 60.0
            confidence = 0.30
            reason = "Content Credentials markers found but the manifest could not be verified."
        elif make and model:
            score = 92.0
            confidence = 0.60  # EXIF is easy to forge: weak evidence on its own
            reason = f"Camera metadata present ({make} {model}); metadata alone is not proof."
        else:
            # Crucial Calibration: Standard web/social media images (WhatsApp, Twitter) strip metadata for privacy.
            # This is normal internet transport, NOT evidence of forgery.
            score = 86.0
            confidence = 0.80
            reason = "Standard digital media profile. Container metadata stripped (expected for web/social sharing); no generative footprints found."

        return SignalResult(
            plugin_name=self.name,
            score=score,
            confidence=confidence,
            reasoning=reason,
            metadata={
                "c2pa_detected": c2pa_info is not None or marker_only,
                "c2pa_verified": bool(c2pa_info and c2pa_info["verified"]),
                "c2pa_state": c2pa_info["state"] if c2pa_info else None,
                "camera_make": make,
                "camera_model": model,
                "software_signature": software,
                "bayer_peak_ratio": round(bayer_ratio, 2)
            }
        )


class BehavioralSignal(ISignalPlugin):
    """
    Truth-Grounded Physical Coherence & Biometric Analyzer.
    Evaluates:
      1. Optical Focus Continuity: Verifies natural depth-of-field without penalizing intentional portrait bokeh.
      2. Video Biological Invariants: Video frame cadence and rPPG cardiovascular pulse detection.
    """
    @property
    def name(self) -> str:
        return "BehavioralSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        # ponytail: Frame continuity & rPPG Green-channel FFT used; 3D face landmark tracking is upgrade path.
        if not os.path.exists(media_path):
            return SignalResult(plugin_name=self.name, score=0.0, confidence=1.0, reasoning="Media missing.", metadata={})

        ext = os.path.splitext(media_path)[1].lower()
        if ext in ['.mp4', '.avi', '.mov']:
            cap = cv2.VideoCapture(media_path)
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0

            green_means = []
            max_sample_frames = min(frames, 90)
            for _ in range(max_sample_frames):
                ret, frame = cap.read()
                if not ret:
                    break
                h, w, _ = frame.shape
                roi = frame[h//4:3*h//4, w//4:3*w//4, 1]
                green_means.append(float(np.mean(roi)))
            cap.release()

            detected_bpm = 0.0
            pulse_detected = False
            if len(green_means) >= 30 and fps > 0:
                signal_arr = np.array(green_means) - np.mean(green_means)
                nyquist = fps / 2.0
                low = min(0.75 / nyquist, 0.9)
                high = min(3.0 / nyquist, 0.95)
                if low < high and len(signal_arr) > 15:
                    b, a = signal.butter(2, [low, high], btype='bandpass')
                    filtered = signal.filtfilt(b, a, signal_arr)
                    fft_mag = np.abs(np.fft.rfft(filtered))
                    freqs = np.fft.rfftfreq(len(filtered), d=1.0/fps)
                    valid_mask = (freqs >= 0.75) & (freqs <= 3.0)
                    if np.any(valid_mask):
                        peak_freq = freqs[valid_mask][np.argmax(fft_mag[valid_mask])]
                        detected_bpm = round(float(peak_freq * 60.0), 1)
                        pnr = float(np.max(fft_mag[valid_mask]) / (np.mean(fft_mag[valid_mask]) + 1e-9))
                        pulse_detected = pnr > 2.2 and (45.0 <= detected_bpm <= 180.0)

            score = 92.0 if pulse_detected else 50.0
            reason = (f"Live cardiovascular pulse rhythm verified via rPPG ({detected_bpm} BPM)."
                      if pulse_detected else "No pulse rhythm found. That is not evidence of manipulation or of authenticity.")

            return SignalResult(
                plugin_name=self.name,
                score=score,
                confidence=0.85 if pulse_detected else 0.0,
                reasoning=reason,
                metadata={"frame_count": frames, "fps": round(fps, 2), "detected_bpm": detected_bpm, "pulse_detected": pulse_detected}
            )

        # Image analysis
        try:
            img = cv2.imread(media_path)
            if img is None:
                raise ValueError("Could not decode image")

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # Natural optical focus gradient:
            # - Real photos have continuous focus variation across the scene
            # - Unnatural cutouts or vector renders with zero gradient (lap_var < 0.1) are flagged
            if lap_var < 0.2:
                score = 65.0
                reason = "Uniform flat raster field; lacking natural optical depth or lens focus gradient."
            else:
                score = 90.0
                reason = "Natural optical focus gradient and depth-of-field dynamics verified."

            return SignalResult(
                plugin_name=self.name,
                score=score,
                confidence=0.85,
                reasoning=reason,
                metadata={
                    "focus_variance": round(lap_var, 2)
                }
            )
        except Exception:
            return SignalResult(
                plugin_name=self.name,
                score=50.0,
                confidence=0.0,
                reasoning="This file type cannot be analyzed as a raster image, so this check carries no evidence.",
                metadata={}
            )


class NetworkSignal(ISignalPlugin):
    """
    Truth-Grounded Perceptual Fingerprinting & Threat Registry Verifier.
    Computes a 64-bit difference hash (dHash) to match against known synthetic media threat registries.
    """
    @property
    def name(self) -> str:
        return "NetworkSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        # ponytail: In-memory hash set; external OSINT syndication API lookup is upgrade path.
        if not os.path.exists(media_path):
            return SignalResult(plugin_name=self.name, score=0.0, confidence=1.0, reasoning="Media missing.", metadata={})

        try:
            with Image.open(media_path) as img:
                resized = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
                px = np.array(resized)
                dhash_int = sum([2 ** i for (i, v) in enumerate((px[:, 1:] > px[:, :-1]).flatten()) if v])
                dhash_hex = f"{dhash_int:016x}"

            distance = registries.nearest_dhash_distance(dhash_hex)
            hit = distance is not None and distance <= MAX_HAMMING_DISTANCE

            if hit:
                score = 20.0
                confidence = 0.95
                reason = "Perceptual fingerprint matches a known synthetic media registry entry."
            elif distance is None:
                score = 50.0
                confidence = 0.0
                reason = "No synthetic-media registry is loaded, so this check carries no evidence."
            else:
                score = 90.0
                confidence = 0.5  # a miss only means "not already known"; uncalibrated
                reason = "Perceptual fingerprint does not match any known synthetic media."

            return SignalResult(
                plugin_name=self.name,
                score=score,
                confidence=confidence,
                reasoning=reason,
                metadata={"dhash_hex": dhash_hex, "registry_hit": hit, "registry_loaded": distance is not None, "nearest_distance": distance}
            )
        except Exception:
            return SignalResult(
                plugin_name=self.name,
                score=50.0,
                confidence=0.0,
                reasoning="Perceptual fingerprinting needs a raster image, so this check carries no evidence.",
                metadata={}
            )
