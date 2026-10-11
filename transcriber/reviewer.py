"""Create a structured study reviewer with a local Ollama model."""

from __future__ import annotations

import json
import re
from collections import Counter
from threading import Event

import requests


MAX_REVIEW_INPUT = 24_000

STOP_WORDS = {
    "about", "after", "again", "also", "because", "before", "being", "between",
    "could", "does", "during", "each", "from", "have", "into", "lecture", "more",
    "other", "screen", "should", "some", "speaker", "than", "that", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "using", "very",
    "what", "when", "where", "which", "while", "with", "would", "your",
}


def prepare_reviewer_source(text: str, limit: int = MAX_REVIEW_INPUT) -> tuple[str, bool]:
    """Keep short transcripts whole and sample long ones across their full length."""
    text = text.strip()
    if len(text) <= limit:
        return text, False
    part = limit // 3
    middle_start = max(0, (len(text) - part) // 2)
    sampled = "\n\n[Later section]\n\n".join(
        (text[:part], text[middle_start : middle_start + part], text[-part:])
    )
    return sampled, True


class LocalReviewer:
    def __init__(self, model: str = "gemma3:4b") -> None:
        self.model = model

    @staticmethod
    def is_available() -> bool:
        try:
            return requests.get("http://127.0.0.1:11434/api/tags", timeout=2).ok
        except requests.RequestException:
            return False

    def generate(self, transcript: str, cancel_event: Event) -> tuple[str, bool]:
        source, sampled = prepare_reviewer_source(transcript)
        sampling_note = (
            "This is a long transcript. State under the title that this is a Quick Reviewer "
            "based on selected sections of the lecture."
            if sampled
            else "Use the complete transcript."
        )
        prompt = f"""Create a clear student reviewer using only the lecture transcript below.
Do not invent facts. Use simple language. {sampling_note}

Return exactly these headings in this order:
## Lesson Summary
## Important Topics
## Terms to Remember
## Mnemonics and Memory Aids
## Review Questions
## Quick Recall Checklist

Under Terms to Remember, give each term and a short meaning. Create useful mnemonics only
when the transcript supports them. Provide 5 to 10 review questions without answers.

LECTURE TRANSCRIPT:
{source}
"""
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": self.model,
                "stream": True,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.2, "num_predict": 1200},
            },
            stream=True,
            timeout=(5, 60),
        )
        response.raise_for_status()
        pieces: list[str] = []
        for line in response.iter_lines():
            if cancel_event.is_set():
                response.close()
                raise InterruptedError("Reviewer creation cancelled.")
            if not line:
                continue
            payload = json.loads(line)
            pieces.append(payload.get("message", {}).get("content", ""))
        reviewer = "".join(pieces).strip()
        if not reviewer:
            raise RuntimeError("Ollama returned an empty reviewer.")
        return reviewer, sampled


class SimpleReviewer:
    """Immediate no-download reviewer used when Ollama is unavailable."""

    def generate(self, transcript: str, cancel_event: Event) -> tuple[str, bool]:
        source, sampled = prepare_reviewer_source(transcript)
        if cancel_event.is_set():
            raise InterruptedError("Reviewer creation cancelled.")
        cleaned = re.sub(r"\[[^\]]+\]", " ", source)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        sentences = [
            item.strip(" -")
            for item in re.split(r"(?<=[.!?])\s+", cleaned)
            if len(item.strip()) >= 25
        ]
        words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", cleaned.casefold())
        terms = [
            word for word, _count in Counter(
                word for word in words if word not in STOP_WORDS
            ).most_common(8)
        ]
        summary = sentences[:5] or ([cleaned[:700]] if cleaned else ["No readable content found."])
        term_lines = []
        for term in terms:
            example = next((s for s in sentences if term in s.casefold()), "")
            meaning = example[:180] + ("…" if len(example) > 180 else "")
            term_lines.append(f"- {term.title()}: {meaning or 'Review this important lecture term.'}")
        memory_terms = terms[:5]
        initials = "".join(term[0].upper() for term in memory_terms)
        mnemonic = (
            f"- Remember **{initials}**: " + ", ".join(term.title() for term in memory_terms)
            if memory_terms else "- Review the main ideas in the lesson summary."
        )
        questions = [f"- What does {term.title()} mean in this lesson?" for term in terms[:5]]
        if not questions:
            questions = ["- What is the main idea of this lecture?"]
        note = (
            "\n*Quick reviewer based on selected sections of the long transcript.*\n"
            if sampled else ""
        )
        output = [
            "## Lesson Summary", note,
            *[f"- {sentence}" for sentence in summary],
            "\n## Important Topics", *[f"- {term.title()}" for term in terms[:6]],
            "\n## Terms to Remember", *(term_lines or ["- Review the lesson summary."]),
            "\n## Mnemonics and Memory Aids", mnemonic,
            "\n## Review Questions", *questions,
            "\n## Quick Recall Checklist",
            "- I can explain the main lesson in my own words.",
            "- I can define the important terms.",
            "- I can answer the review questions without looking at the transcript.",
        ]
        return "\n".join(output).strip(), sampled
