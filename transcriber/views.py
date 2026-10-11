"""Build display text for each transcript output mode."""

from __future__ import annotations

from .models import TranscriptionResult
from .utils import format_timestamp

COMBINED = "Combined context"
AUDIO_ONLY = "Audio only"
SCREEN_ONLY = "Screen context"
REVIEWER = "Reviewer"
OUTPUT_MODES = (COMBINED, AUDIO_ONLY, SCREEN_ONLY, REVIEWER)


def render_result_text(result: TranscriptionResult, mode: str) -> str:
    lines: list[str] = []

    if mode == AUDIO_ONLY:
        segments = result.segments
        if not segments:
            for block in result.blocks:
                lines.append(
                    f"[{format_timestamp(block.start)} - {format_timestamp(block.end)}] "
                    f"{block.speech}"
                )
                lines.append("")
        else:
            for segment in segments:
                lines.append(
                    f"[{format_timestamp(segment.start)} - {format_timestamp(segment.end)}] "
                    f"{segment.text}"
                )
                lines.append("")
        return "\n".join(lines).rstrip()

    if mode == SCREEN_ONLY:
        contexts = result.screen_contexts
        if contexts:
            for context in contexts:
                lines.append(
                    f"[{format_timestamp(context.timestamp)}] "
                    f"Screen ({context.source}): {context.text}"
                )
                lines.append("")
        else:
            for block in result.blocks:
                if block.screen_context:
                    lines.append(
                        f"[{format_timestamp(block.start)}] "
                        f"Screen ({block.context_source}): {block.screen_context}"
                    )
                    lines.append("")
        return "\n".join(lines).rstrip()

    for block in result.blocks:
        lines.append(
            f"[{format_timestamp(block.start)} - {format_timestamp(block.end)}] "
            f"{block.speech}"
        )
        if block.screen_context:
            lines.append(f"    Screen ({block.context_source}): {block.screen_context}")
        lines.append("")
    return "\n".join(lines).rstrip()
