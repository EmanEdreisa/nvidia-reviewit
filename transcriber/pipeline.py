"""End-to-end orchestration for transcription and screen understanding."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Event

from .merge import merge_transcript_and_context
from .models import PipelineOptions, TranscriptSegment, TranscriptionResult
from .speech import SpeechTranscriber
from .vision import ScreenAnalyzer

ProgressCallback = Callable[[float, str], None]
SegmentCallback = Callable[[TranscriptSegment], None]


def run_pipeline(
    video_path: Path,
    options: PipelineOptions,
    progress: ProgressCallback,
    cancel_event: Event,
    segment_callback: SegmentCallback | None = None,
) -> TranscriptionResult:
    if not video_path.is_file():
        raise FileNotFoundError("Select an existing video file.")

    project_root = Path(__file__).resolve().parent.parent
    speech = SpeechTranscriber(
        model_name=options.whisper_model,
        use_gpu=options.use_gpu,
        model_dir=project_root / "models" / "whisper",
    )
    segments, language, duration = speech.transcribe(
        video_path,
        options.language,
        progress,
        cancel_event,
        segment_callback,
        options.processing_mode,
    )

    analyzer = ScreenAnalyzer(
        interval_seconds=options.frame_interval_seconds,
        max_frames=options.max_context_frames,
        use_ollama=options.use_ollama,
        ollama_model=options.ollama_model,
    )
    contexts = analyzer.analyze(video_path, duration, progress, cancel_event)
    progress(0.97, "Combining audio and screen context...")
    blocks = merge_transcript_and_context(segments, contexts)
    progress(1.0, "Transcription complete.")
    return TranscriptionResult(
        video_path=video_path,
        language=language,
        duration=duration,
        blocks=blocks,
        segments=segments,
        screen_contexts=contexts,
    )
