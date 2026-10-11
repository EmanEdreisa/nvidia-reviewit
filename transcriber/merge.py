"""Combine time-aligned speech segments with changing screen context."""

from __future__ import annotations

from .models import ContextualBlock, ScreenContext, TranscriptSegment


def merge_transcript_and_context(
    segments: list[TranscriptSegment], contexts: list[ScreenContext]
) -> list[ContextualBlock]:
    if not segments:
        return []

    contexts = sorted(contexts, key=lambda item: item.timestamp)
    context_index = -1
    last_emitted_context = -1
    blocks: list[ContextualBlock] = []

    for segment in segments:
        while (
            context_index + 1 < len(contexts)
            and contexts[context_index + 1].timestamp <= segment.end
        ):
            context_index += 1

        screen_text = None
        screen_source = None
        if context_index >= 0 and context_index != last_emitted_context:
            screen_text = contexts[context_index].text
            screen_source = contexts[context_index].source
            last_emitted_context = context_index

        blocks.append(
            ContextualBlock(
                start=segment.start,
                end=segment.end,
                speech=segment.text,
                screen_context=screen_text,
                context_source=screen_source,
            )
        )

    return blocks
