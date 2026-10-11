"""Modern HTML interface hosted in a native pywebview window."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .exporters import (
    export_pdf,
    export_reviewer_pdf,
    export_reviewer_word,
    export_word,
)
from .models import PipelineOptions, TranscriptionResult
from .pipeline import run_pipeline
from .reviewer import LocalReviewer, SimpleReviewer
from .utils import format_timestamp
from .views import AUDIO_ONLY, COMBINED, REVIEWER, SCREEN_ONLY, render_result_text


VIDEO_TYPES = (
    "Video files (*.mp4;*.mkv;*.mov;*.avi;*.webm;*.m4v)",
    "All files (*.*)",
)


class WebApi:
    def __init__(self) -> None:
        # Keep the native window private so pywebview does not expose and
        # recursively serialize its large object graph to JavaScript.
        self._window = None
        self.video_path: Path | None = None
        self.result: TranscriptionResult | None = None
        self.cancel_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._reviewer_worker: threading.Thread | None = None
        self.reviewer_text = ""
        self._ollama_model = "gemma3:4b"

    def _emit(self, event: dict[str, Any]) -> None:
        if not self._window:
            return
        payload = json.dumps(event, ensure_ascii=False).replace("</", "<\\/")
        try:
            self._window.evaluate_js(f"window.app.receiveEvent({payload})")
        except Exception:
            # The window may already be closing.
            pass

    def select_video(self) -> dict[str, Any]:
        import webview

        selected = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=VIDEO_TYPES,
        )
        if not selected:
            return {"ok": False}
        self.video_path = Path(selected[0])
        return {
            "ok": True,
            "name": self.video_path.name,
            "path": str(self.video_path),
            "size": self.video_path.stat().st_size,
        }

    def start_transcription(self, raw: dict[str, Any]) -> dict[str, Any]:
        if self._worker and self._worker.is_alive():
            return {"ok": False, "error": "A transcription is already running."}
        if not self.video_path or not self.video_path.is_file():
            return {"ok": False, "error": "Select a video first."}

        try:
            interval = float(raw.get("interval", 45))
            if not 5 <= interval <= 120:
                raise ValueError
            language = str(raw.get("language", "auto")).strip()
            if not language or language.casefold() == "auto":
                language = None
            options = PipelineOptions(
                whisper_model=str(raw.get("model", "small")),
                language=language,
                use_gpu=bool(raw.get("use_gpu", False)),
                frame_interval_seconds=interval,
                use_ollama=bool(raw.get("use_ollama", False)),
                ollama_model=str(raw.get("ollama_model", "gemma3:4b")).strip()
                or "gemma3:4b",
                processing_mode=str(raw.get("processing_mode", "balanced")),
            )
        except (TypeError, ValueError):
            return {"ok": False, "error": "Screen interval must be between 5 and 120 seconds."}

        self.result = None
        self.reviewer_text = ""
        self._ollama_model = options.ollama_model
        self.cancel_event.clear()
        self._worker = threading.Thread(
            target=self._run_worker,
            args=(self.video_path, options),
            daemon=True,
        )
        self._worker.start()
        return {"ok": True}

    def _run_worker(self, path: Path, options: PipelineOptions) -> None:
        try:
            result = run_pipeline(
                path,
                options,
                lambda value, status: self._emit(
                    {"type": "progress", "value": value, "status": status}
                ),
                self.cancel_event,
                lambda segment: self._emit(
                    {
                        "type": "segment",
                        "start": format_timestamp(segment.start),
                        "end": format_timestamp(segment.end),
                        "text": segment.text,
                    }
                ),
            )
            self.result = result
            self._emit(
                {
                    "type": "complete",
                    "language": result.language,
                    "duration": format_timestamp(result.duration),
                    "audio_count": len(result.segments),
                    "screen_count": len(result.screen_contexts),
                    "views": {
                        COMBINED: render_result_text(result, COMBINED),
                        AUDIO_ONLY: render_result_text(result, AUDIO_ONLY),
                        SCREEN_ONLY: render_result_text(result, SCREEN_ONLY),
                    },
                }
            )
        except InterruptedError as error:
            self._emit({"type": "cancelled", "message": str(error)})
        except Exception as error:
            self._emit({"type": "error", "message": str(error)})

    def cancel(self) -> dict[str, bool]:
        self.cancel_event.set()
        return {"ok": True}

    def create_reviewer(self) -> dict[str, Any]:
        if not self.result:
            return {"ok": False, "error": "Finish a transcription first."}
        if self._reviewer_worker and self._reviewer_worker.is_alive():
            return {"ok": False, "error": "A reviewer is already being created."}
        local_ai = LocalReviewer(self._ollama_model)
        uses_ollama = local_ai.is_available()
        reviewer = local_ai if uses_ollama else SimpleReviewer()
        self.cancel_event.clear()
        transcript = render_result_text(self.result, COMBINED)
        self._reviewer_worker = threading.Thread(
            target=self._run_reviewer,
            args=(reviewer, transcript, uses_ollama),
            daemon=True,
        )
        self._reviewer_worker.start()
        return {"ok": True}

    def _run_reviewer(
        self, reviewer: LocalReviewer | SimpleReviewer, transcript: str, uses_ollama: bool
    ) -> None:
        try:
            self._emit({"type": "reviewer_progress", "uses_ollama": uses_ollama})
            try:
                content, sampled = reviewer.generate(transcript, self.cancel_event)
            except InterruptedError:
                raise
            except Exception:
                if not uses_ollama:
                    raise
                # Ollama may be running without the requested model or with an
                # older endpoint. The demonstration reviewer must still work.
                reviewer = SimpleReviewer()
                uses_ollama = False
                self._emit(
                    {
                        "type": "reviewer_fallback",
                        "message": "Ollama was unavailable; creating the simple reviewer instead.",
                    }
                )
                content, sampled = reviewer.generate(transcript, self.cancel_event)
            self.reviewer_text = content
            self._emit(
                {
                    "type": "reviewer_complete",
                    "content": content,
                    "sampled": sampled,
                    "uses_ollama": uses_ollama,
                }
            )
        except InterruptedError as error:
            self._emit({"type": "reviewer_cancelled", "message": str(error)})
        except Exception as error:
            self._emit({"type": "reviewer_error", "message": str(error)})

    def export(self, file_format: str, mode: str) -> dict[str, Any]:
        import webview

        if not self.result:
            return {"ok": False, "error": "Finish a transcription before exporting."}
        if mode not in (COMBINED, AUDIO_ONLY, SCREEN_ONLY, REVIEWER):
            mode = COMBINED
        extension = ".docx" if file_format == "word" else ".pdf"
        label = "Word document (*.docx)" if file_format == "word" else "PDF document (*.pdf)"
        safe_mode = mode.replace(" ", "_").lower()
        selected = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=f"{self.result.video_path.stem}_{safe_mode}{extension}",
            file_types=(label,),
        )
        if not selected:
            return {"ok": False, "cancelled": True}
        destination = Path(selected[0] if isinstance(selected, (list, tuple)) else selected)
        if destination.suffix.casefold() != extension:
            destination = destination.with_suffix(extension)
        try:
            if mode == REVIEWER:
                if not self.reviewer_text:
                    return {"ok": False, "error": "Create the reviewer before exporting it."}
                if file_format == "word":
                    export_reviewer_word(self.reviewer_text, destination)
                else:
                    export_reviewer_pdf(self.reviewer_text, destination)
            elif file_format == "word":
                export_word(self.result, destination, mode)
            else:
                export_pdf(self.result, destination, mode)
            return {"ok": True, "path": str(destination)}
        except Exception as error:
            return {"ok": False, "error": str(error)}


class TranscriberApp:
    def __init__(self) -> None:
        self.api = WebApi()

    def run(self) -> None:
        import webview

        page = Path(__file__).resolve().parent / "web" / "index.html"
        window = webview.create_window(
            "Review It — Lecture Transcriber and Reviewer",
            url=page.as_uri(),
            js_api=self.api,
            width=1240,
            height=820,
            min_size=(960, 650),
            background_color="#071426",
        )
        self.api._window = window
        webview.start(debug=False)
