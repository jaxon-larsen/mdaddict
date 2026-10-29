"""Decimal corruption must not become publication-eligible source evidence."""
import pytest

from mdaddict import ExtractOptions, ExtractionIssue, extract
from mdaddict.extract_offline import missing_decimal_tokens


@pytest.mark.parametrize("native,markdown,missing", [
    ("Count 1.1M", "| Count | 11M<br>.<br>1M |", ["1.1"]),
    ("Trials 1.1 and 1.1", "Trial 1.1", ["1.1"]),
    ("Reading 0.05.", "Reading 005.", ["0.05"]),
    ("Reading 1.1 M", r"Reading $1.1$ M", []),
    ("Reading 1.1M", "Reading **1.1** M", []),
    ("Version 1.2.3", "Version 1.2.3", []),
    ("Count 11", "Count 11", []),
])
def test_decimal_groups_and_multiplicity(native, markdown, missing):
    assert missing_decimal_tokens(native, markdown) == missing


def test_numeric_hold_survives_a_legacy_severity():
    issue = ExtractionIssue("pdf_numeric_unresolved", "Changed decimal", block_ids=["page:1"], severity="informational")
    assert issue.severity == "unresolved"


def test_compatibility_decimal_corruption_is_scoped_and_cached(tmp_path, monkeypatch):
    pymupdf = pytest.importorskip("pymupdf")
    pymupdf4llm = pytest.importorskip("pymupdf4llm")
    path = tmp_path / "counts.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "The corpus contains 1.1M entries.")
        document.new_page().insert_text((72, 72), "The second page preserves its material.")
        document.save(path)

    def converted(*args, **kwargs):
        if kwargs["pages"] == [0]:
            return "| Corpus | Entries |\n|---|---|\n| Observed | 11M<br>.<br>1M |"
        return "The second page preserves its material."

    monkeypatch.setattr(pymupdf4llm, "to_markdown", converted)
    options = ExtractOptions(pdf_backend="pymupdf", ocr="off", max_ai_requests=0)
    first = extract(path, options=options, out_dir=tmp_path / "out")
    issues = [i for i in first.issues if i.code == "pdf_numeric_unresolved"]
    assert len(issues) == 1 and issues[0].block_ids == ["page:1"]
    assert issues[0].source.index == 1 and issues[0].severity == "unresolved"
    # A labeled native recovery must not make the wrong table safe to publish.
    assert "11M<br>.<br>1M" in first.markdown and "1.1M" in first.markdown
    assert first.status == "partial" and first.usage.get("requests", 0) == 0
    first.validate_contract()
    again = extract(path, options=options, out_dir=tmp_path / "out")
    assert again.cache_hit and again.issues == first.issues
    assert again.blocks == first.blocks
