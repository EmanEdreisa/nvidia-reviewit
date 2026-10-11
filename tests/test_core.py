from pathlib import Path
import unittest
from threading import Event
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from transcriber.merge import merge_transcript_and_context
from transcriber.models import (
    ContextualBlock,
    ScreenContext,
    TranscriptSegment,
    TranscriptionResult,
)
from transcriber.utils import clean_text, deduplicate_lines, format_timestamp
from transcriber.models import PipelineOptions
from transcriber.exporters import export_reviewer_pdf, export_reviewer_word
from transcriber.reviewer import LocalReviewer, SimpleReviewer, prepare_reviewer_source
from transcriber.web_ui import WebApi
from transcriber.views import AUDIO_ONLY, COMBINED, SCREEN_ONLY, render_result_text


class UtilityTests(unittest.TestCase):
    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(3661.9), "01:01:01")
        self.assertEqual(format_timestamp(-4), "00:00:00")

    def test_text_cleanup(self):
        self.assertEqual(clean_text("  a\n  b  "), "a b")
        self.assertEqual(deduplicate_lines(["Slide 1", "slide 1", "Topic"]), "Slide 1 | Topic")


class MergeTests(unittest.TestCase):
    def test_context_is_emitted_once_when_it_changes(self):
        segments = [
            TranscriptSegment(0, 4, "Opening"),
            TranscriptSegment(4, 9, "Details"),
            TranscriptSegment(9, 14, "Next topic"),
        ]
        contexts = [
            ScreenContext(0, "Title slide"),
            ScreenContext(10, "Diagram"),
        ]
        blocks = merge_transcript_and_context(segments, contexts)
        self.assertEqual(blocks[0].screen_context, "Title slide")
        self.assertIsNone(blocks[1].screen_context)
        self.assertEqual(blocks[2].screen_context, "Diagram")

    def test_empty_contexts_keep_transcript(self):
        segments = [TranscriptSegment(1, 2, "Hello")]
        blocks = merge_transcript_and_context(segments, [])
        self.assertEqual(blocks[0].speech, "Hello")
        self.assertIsNone(blocks[0].screen_context)


class PerformanceOptionTests(unittest.TestCase):
    def test_balanced_processing_is_the_default(self):
        self.assertEqual(PipelineOptions().processing_mode, "balanced")


class ReviewerTests(unittest.TestCase):
    def test_short_source_is_not_sampled(self):
        source, sampled = prepare_reviewer_source("Complete short lecture")
        self.assertEqual(source, "Complete short lecture")
        self.assertFalse(sampled)

    def test_long_source_samples_start_middle_and_end(self):
        text = "A" * 100 + "B" * 100 + "C" * 100
        source, sampled = prepare_reviewer_source(text, limit=90)
        self.assertTrue(sampled)
        self.assertIn("A" * 20, source)
        self.assertIn("B" * 20, source)
        self.assertIn("C" * 20, source)

    @patch("transcriber.reviewer.requests.post")
    def test_local_reviewer_returns_required_sections(self, post):
        headings = (
            "## Lesson Summary\nSummary\n## Important Topics\n- Topic\n"
            "## Terms to Remember\n- Term: meaning\n"
            "## Mnemonics and Memory Aids\n- Memory aid\n"
            "## Review Questions\n- Question?\n"
            "## Quick Recall Checklist\n- Recall"
        )
        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = [
            ('{"message":{"content":' + __import__("json").dumps(headings) + '}}').encode()
        ]
        post.return_value = response
        content, sampled = LocalReviewer().generate("Lecture content", Event())
        self.assertFalse(sampled)
        for heading in (
            "Lesson Summary", "Important Topics", "Terms to Remember",
            "Mnemonics and Memory Aids", "Review Questions", "Quick Recall Checklist",
        ):
            self.assertIn(heading, content)

    def test_simple_reviewer_has_all_sections_without_ollama(self):
        content, sampled = SimpleReviewer().generate(
            "Photosynthesis changes light energy into chemical energy. "
            "Plants use chlorophyll to capture light energy.",
            Event(),
        )
        self.assertFalse(sampled)
        for heading in (
            "Lesson Summary", "Important Topics", "Terms to Remember",
            "Mnemonics and Memory Aids", "Review Questions", "Quick Recall Checklist",
        ):
            self.assertIn(heading, content)

    @patch("transcriber.web_ui.LocalReviewer.generate", side_effect=RuntimeError("404"))
    def test_ollama_failure_falls_back_to_simple_reviewer(self, _generate):
        api = WebApi()
        api.result = TranscriptionResult(
            Path("lecture.mp4"),
            "en",
            10,
            segments=[TranscriptSegment(0, 5, "Plants convert light into chemical energy.")],
        )
        api._run_reviewer(LocalReviewer(), "Plants convert light into chemical energy.", True)
        self.assertIn("Lesson Summary", api.reviewer_text)

    def test_reviewer_exports_word_and_pdf(self):
        content = "## Lesson Summary\nA summary\n## Terms to Remember\n- Term: meaning"
        with TemporaryDirectory(dir=Path.cwd()) as folder:
            word = Path(folder) / "reviewer.docx"
            pdf = Path(folder) / "reviewer.pdf"
            export_reviewer_word(content, word)
            export_reviewer_pdf(content, pdf)
            self.assertGreater(word.stat().st_size, 0)
            self.assertGreater(pdf.stat().st_size, 0)


class OutputViewTests(unittest.TestCase):
    def setUp(self):
        self.result = TranscriptionResult(
            video_path=Path("lecture.mp4"),
            language="en",
            duration=10,
            blocks=[ContextualBlock(0, 5, "Spoken words", "Slide title", "OCR")],
            segments=[TranscriptSegment(0, 5, "Spoken words")],
            screen_contexts=[ScreenContext(0, "Slide title", "OCR")],
        )

    def test_combined_view_contains_audio_and_screen(self):
        text = render_result_text(self.result, COMBINED)
        self.assertIn("Spoken words", text)
        self.assertIn("Slide title", text)

    def test_audio_view_excludes_screen(self):
        text = render_result_text(self.result, AUDIO_ONLY)
        self.assertIn("Spoken words", text)
        self.assertNotIn("Slide title", text)

    def test_screen_view_excludes_audio(self):
        text = render_result_text(self.result, SCREEN_ONLY)
        self.assertIn("Slide title", text)
        self.assertNotIn("Spoken words", text)


if __name__ == "__main__":
    unittest.main()
