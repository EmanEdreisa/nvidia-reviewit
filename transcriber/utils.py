"""Small formatting and text-cleaning helpers."""

from __future__ import annotations

import re


def format_timestamp(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def deduplicate_lines(lines: list[str]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        cleaned = clean_text(line)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return " | ".join(output)
