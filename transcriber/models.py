"""Shared data structures for the transcription pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class ScreenContext:
    timestamp: float
    text: str
    source: str = "OCR"


@dataclass(frozen=True)
class ContextualBlock:
    start: float
    end: float
    speech: str
    screen_context: str | None = None
    context_source: str | None = None


@dataclass
class TranscriptionResult:
    video_path: Path
    language: str
    duration: float
    blocks: list[ContextualBlock] = field(default_factory=list)
    segments: list[TranscriptSegment] = field(default_factory=list)
    screen_contexts: list[ScreenContext] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineOptions:
    whisper_model: str = "small"
    language: str | None = None
    use_gpu: bool = False
    frame_interval_seconds: float = 20.0
    use_ollama: bool = True
    ollama_model: str = "gemma3:4b"
    max_context_frames: int = 120
    processing_mode: str = "balanced"
