"""Offline speech recognition using faster-whisper."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from threading import Event

from .models import TranscriptSegment
from .utils import clean_text

ProgressCallback = Callable[[float, str], None]
SegmentCallback = Callable[[TranscriptSegment], None]


class SpeechTranscriber:
    def __init__(self, model_name: str, use_gpu: bool, model_dir: Path) -> None:
        self.model_name = model_name
        self.use_gpu = use_gpu
        self.model_dir = model_dir

    def _load_model(self, progress: ProgressCallback):
        from faster_whisper import WhisperModel

        self.model_dir.mkdir(parents=True, exist_ok=True)
        if self.use_gpu:
            progress(0.03, "Loading speech model on NVIDIA GPU...")
            try:
                return WhisperModel(
                    self.model_name,
                    device="cuda",
                    compute_type="float16",
                    download_root=str(self.model_dir),
                )
            except Exception as error:
                progress(0.03, f"GPU unavailable; using CPU ({error})")

        progress(0.03, "Loading speech model on CPU...")
        logical_processors = os.cpu_count() or 4
        cpu_threads = max(4, min(10, logical_processors - 2))
        return WhisperModel(
            self.model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
            download_root=str(self.model_dir),
        )

    def transcribe(
        self,
        video_path: Path,
        language: str | None,
        progress: ProgressCallback,
        cancel_event: Event,
        segment_callback: SegmentCallback | None = None,
        processing_mode: str = "balanced",
    ) -> tuple[list[TranscriptSegment], str, float]:
        model = self._load_model(progress)
        mode = processing_mode.casefold()
        beam_size = {"fast": 1, "balanced": 2, "accurate": 5}.get(mode, 2)
        segments, info = model.transcribe(
            str(video_path),
            language=language,
            beam_size=beam_size,
            vad_filter=True,
            condition_on_previous_text=mode == "accurate",
            word_timestamps=False,
        )

        duration = float(getattr(info, "duration", 0.0) or 0.0)
        detected_language = str(getattr(info, "language", language or "unknown"))
        output: list[TranscriptSegment] = []

        for segment in segments:
            if cancel_event.is_set():
                raise InterruptedError("Transcription cancelled.")
            text = clean_text(segment.text)
            if text:
                output.append(
                    TranscriptSegment(
                        start=float(segment.start),
                        end=float(segment.end),
                        text=text,
                    )
                )
                if segment_callback:
                    segment_callback(output[-1])
            ratio = min(1.0, float(segment.end) / duration) if duration else 0.0
            progress(0.05 + ratio * 0.50, "Transcribing lecture audio...")

        return output, detected_language, duration
