"""Screen-frame sampling, OCR, and optional local multimodal analysis."""

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path
from threading import Event

from .models import ScreenContext
from .utils import clean_text, deduplicate_lines

ProgressCallback = Callable[[float, str], None]


class LocalVisionClient:
    """Calls Ollama on localhost. No cloud service or API key is used."""

    def __init__(self, model: str, timeout_seconds: int = 180) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def is_available() -> bool:
        import requests

        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
            return response.ok
        except requests.RequestException:
            return False

    def analyze(self, jpeg_bytes: bytes, ocr_text: str) -> str:
        import requests

        prompt = (
            "Describe the lecture content visible on this screen in one concise sentence. "
            "Keep technical terms, formulas, labels, and code names. Do not mention that this is an image."
        )
        if ocr_text:
            prompt += f" OCR text for reference: {ocr_text}"

        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [base64.b64encode(jpeg_bytes).decode("ascii")],
                    }
                ],
                "options": {"temperature": 0.1},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return clean_text(payload.get("message", {}).get("content", ""))


class ScreenAnalyzer:
    def __init__(
        self,
        interval_seconds: float,
        max_frames: int,
        use_ollama: bool,
        ollama_model: str,
    ) -> None:
        self.interval_seconds = max(2.0, interval_seconds)
        self.max_frames = max(1, max_frames)
        self.use_ollama = use_ollama
        self.ollama_model = ollama_model

    @staticmethod
    def _scene_changed(previous, current, threshold: float = 12.0) -> bool:
        if previous is None:
            return True
        import cv2
        import numpy as np

        prior = cv2.resize(previous, (160, 90))
        present = cv2.resize(current, (160, 90))
        difference = np.mean(cv2.absdiff(prior, present))
        return bool(difference >= threshold)

    @staticmethod
    def _ocr(engine, frame) -> str:
        result = engine(frame)
        if not result or result.txts is None or result.scores is None:
            return ""
        lines = [
            text
            for text, score in zip(result.txts, result.scores)
            if float(score) >= 0.50
        ]
        return deduplicate_lines(lines)

    @staticmethod
    def _analysis_frame(frame, max_width: int = 1600):
        """Reduce costly OCR/vision work on 1440p and 4K recordings."""
        if frame.shape[1] <= max_width:
            return frame
        import cv2

        scale = max_width / frame.shape[1]
        return cv2.resize(
            frame,
            (max_width, max(1, round(frame.shape[0] * scale))),
            interpolation=cv2.INTER_AREA,
        )

    def analyze(
        self,
        video_path: Path,
        known_duration: float,
        progress: ProgressCallback,
        cancel_event: Event,
    ) -> list[ScreenContext]:
        import cv2
        from rapidocr import RapidOCR

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError("The selected video could not be opened for screen analysis.")

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        duration = known_duration or (frame_count / fps if fps > 0 else 0.0)
        effective_interval = max(
            self.interval_seconds,
            duration / self.max_frames if duration else self.interval_seconds,
        )
        sample_count = max(1, int(duration / effective_interval) + 1) if duration else 1

        ocr_engine = RapidOCR()
        vision_client = LocalVisionClient(self.ollama_model) if self.use_ollama else None
        ollama_available = bool(vision_client and vision_client.is_available())
        if self.use_ollama and not ollama_available:
            progress(0.56, "Local vision AI is not running; continuing with screen OCR.")
        contexts: list[ScreenContext] = []
        previous_frame = None

        try:
            for index in range(sample_count):
                if cancel_event.is_set():
                    raise InterruptedError("Transcription cancelled.")

                timestamp = min(duration, index * effective_interval) if duration else 0.0
                capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
                ok, frame = capture.read()
                if not ok:
                    continue

                progress(
                    0.55 + ((index + 1) / sample_count) * 0.40,
                    "Reading lecture screen context...",
                )
                if not self._scene_changed(previous_frame, frame):
                    continue
                previous_frame = frame.copy()
                analysis_frame = self._analysis_frame(frame)

                ocr_text = self._ocr(ocr_engine, analysis_frame)
                description = ""
                source = "OCR"

                if vision_client and ollama_available:
                    encoded, jpeg = cv2.imencode(
                        ".jpg", analysis_frame, [cv2.IMWRITE_JPEG_QUALITY, 82]
                    )
                    if encoded:
                        try:
                            description = vision_client.analyze(jpeg.tobytes(), ocr_text)
                            source = f"Local vision AI ({self.ollama_model})"
                        except Exception:
                            ollama_available = False
                            progress(0.56, "Local vision AI unavailable; continuing with screen OCR.")

                combined = description or ocr_text
                if combined:
                    contexts.append(
                        ScreenContext(timestamp=timestamp, text=combined, source=source)
                    )
        finally:
            capture.release()

        return contexts
