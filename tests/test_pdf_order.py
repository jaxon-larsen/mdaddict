"""The qualifier below two columns belongs after both sets of steps."""
from pathlib import Path
from collections import Counter
from copy import deepcopy

import pytest

from mdaddict import ExtractOptions, ExtractionIssue, extract
from mdaddict.pdf_order import reorder_numbered_columns


def test_qualification_follows_all_numbered_steps(tmp_path):
    pytest.importorskip("pymupdf")
    pytest.importorskip("pymupdf4llm")
    path = Path(__file__).parent / "fixtures/ordinary-multi-column.pdf"
    options = ExtractOptions(pdf_backend="pymupdf", ocr="off", max_ai_requests=0)
    result = extract(path, options=options, out_dir=tmp_path / "out")
    passages = [
        "Calibration steps",
        "1. Warm the instrument for ten minutes.",
        "2. Load the blank specimen.",
        "3. Record the baseline reading.",
        "4. Load the sample specimen.",
        "5. Record the sample reading.",
        "6. Subtract the baseline from the sample.",
        "Keep the original units on every recorded value.",
    ]
    positions = [result.markdown.index(text) for text in passages]
    assert positions == sorted(positions)
    assert all(result.markdown.count(text) == 1 for text in passages)
    result.validate_contract()
    assert result.usage.get("requests", 0) == 0
    assert any(i.code == "pdf_reading_order_recovery" for i in result.issues)
    again = extract(path, options=options, out_dir=tmp_path / "out")
    assert again.cache_hit and again.markdown == result.markdown
    assert again.blocks == result.blocks and again.issues == result.issues


def test_unowned_markdown_stays_held_and_cached(tmp_path, monkeypatch):
    pytest.importorskip("pymupdf")
    converter = pytest.importorskip("pymupdf4llm")
    original = converter.to_markdown

    def extra(*args, **kwargs):
        return original(*args, **kwargs) + "\n\nExtra paragraph without native ownership."

    monkeypatch.setattr(converter, "to_markdown", extra)
    path = Path(__file__).parent / "fixtures/ordinary-multi-column.pdf"
    options = ExtractOptions(pdf_backend="pymupdf", ocr="off", max_ai_requests=0)
    result = extract(path, options=options, out_dir=tmp_path / "out")
    issues = [i for i in result.issues if i.code == "pdf_reading_order_unresolved"]
    assert len(issues) == 1 and issues[0].block_ids == ["page:1"]
    assert issues[0].severity == "unresolved" and result.status == "partial"
    assert "Extra paragraph without native ownership." in result.markdown
    assert result.markdown.index("Keep the original units") < result.markdown.index("6. Subtract")
    result.validate_contract()
    again = extract(path, options=options, out_dir=tmp_path / "out")
    assert again.cache_hit and again.markdown == result.markdown and again.issues == result.issues


class NativePage:
    first_annot = first_widget = None

    def __init__(self, paragraphs):
        self.blocks = [{"type": 0, "bbox": [x, y, x+100, y+12],
                        "lines": [{"dir": (1, 0), "spans": [{"text": text}]}]}
                       for text, x, y in paragraphs]

    def get_text(self, kind):
        assert kind == "dict"
        return {"blocks": self.blocks}

    def get_drawings(self):
        return []

    def get_image_info(self):
        return []

    def get_links(self):
        return []


PARAGRAPHS = [("Instructions", 30, 20), ("1. Prepare.", 30, 70), ("2. Measure.", 30, 100),
              ("3. Record.", 200, 70), ("4. Compare.", 200, 100), ("Keep the units (λ).", 30, 180)]
BAD = "# Instructions\n\n1. Prepare.\n\n2. Measure.\n\n**Keep the units (λ).**\n\n3. Record.\n\n4. Compare.\n"


def test_source_insertion_order_is_not_the_numbered_order_proof():
    corrected, reason = reorder_numbered_columns(NativePage(list(reversed(PARAGRAPHS))), BAD)
    assert reason is None and corrected.index("4. Compare.") < corrected.index("**Keep")
    assert Counter(corrected) == Counter(BAD)
    assert corrected.count("**Keep the units (λ).**") == 1


@pytest.mark.parametrize("markdown", [
    BAD + "\n\nExtra native-unowned instructions.",
    BAD + "\n\n**Keep the units (λ).**",
    BAD.replace("2. Measure.", "1. Measure."),
    BAD.replace("2. Measure.", "```\n2. Measure.\n```"),
])
def test_ambiguous_markdown_stays_unchanged(markdown):
    observed, reason = reorder_numbered_columns(NativePage(PARAGRAPHS), markdown)
    assert observed == markdown and reason


@pytest.mark.parametrize("change", ["rotation", "numbering", "interruption", "third-column"])
def test_conflicting_native_geometry_stays_unchanged(change):
    page = NativePage(PARAGRAPHS)
    if change == "rotation":
        page.blocks[2]["lines"][0]["dir"] = (0, 1)
    elif change == "numbering":
        page.blocks[3]["lines"][0]["spans"][0]["text"] = "2. Record."
    elif change == "interruption":
        page.blocks.extend(NativePage([("Intervening condition.", 30, 95)]).blocks)
    else:
        page.blocks.extend(NativePage([("5. Continue.", 360, 70), ("6. Finish.", 360, 100)]).blocks)
    observed, reason = reorder_numbered_columns(page, BAD)
    assert observed == BAD and reason


def test_literal_native_underscore_is_not_ignored_for_ownership():
    paragraphs = deepcopy(PARAGRAPHS)
    paragraphs[-1] = ("Keep A_B.", 30, 180)
    markdown = BAD.replace("**Keep the units (λ).**", "Keep AB.")
    observed, reason = reorder_numbered_columns(NativePage(paragraphs), markdown)
    assert observed == markdown and reason


def test_complex_page_is_left_to_existing_extraction_guards():
    page = NativePage(PARAGRAPHS)
    page.get_drawings = lambda: [{"rect": [0, 0, 10, 10]}]
    assert reorder_numbered_columns(page, BAD) == (BAD, None)


def test_legacy_severity_does_not_clear_an_ordering_hold():
    issue = ExtractionIssue("pdf_reading_order_unresolved", "Ambiguous order", block_ids=["page:1"], severity="informational")
    assert issue.severity == "unresolved"
