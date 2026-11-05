"""Native ruled-cell geometry must preserve merged relationships, not fill them."""
from dataclasses import asdict
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mdaddict import ExtractOptions, ExtractResult, extract
from mdaddict.extract_offline import missing_source_blocks, native_tables


FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = FIXTURES / "table-controls.pdf"
GOLD = json.loads((FIXTURES / "table-controls.json").read_text(encoding="utf-8"))


class Cells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows.append([])
        elif tag in {"td", "th"}:
            attrs = dict(attrs)
            self.cell = ["", int(attrs.get("rowspan", 1)), int(attrs.get("colspan", 1))]
        elif tag == "br" and self.cell is not None:
            self.cell[0] += "\n"

    def handle_data(self, text):
        if self.cell is not None:
            self.cell[0] += text

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.rows[-1].append(tuple(self.cell))
            self.cell = None


def test_source_bound_merged_header_and_empty_values_survive_cache(tmp_path):
    pytest.importorskip("pymupdf4llm")
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == GOLD["source_sha256"]
    options = ExtractOptions(pdf_backend="pymupdf", ocr="off", max_ai_requests=0)
    first = extract(SOURCE, options=options, out_dir=tmp_path / "cache")
    block = next(b for b in first.blocks if b.source.index == 3)
    text = first.markdown[block.start:block.end]
    table = Cells()
    table.feed(text)
    assert table.rows == [
        [("Readings", 1, 2), ("Status", 2, 1)],
        [("Trial A", 1, 1), ("Trial B", 1, 1)],
        [("7", 1, 1), ("0", 1, 1), ("Pass", 1, 1)],
        [("", 1, 1), ("5", 1, 1), ("Hold", 1, 1)],
    ]
    assert text.index("Merged Header") < text.index("<table>") < text.index("Empty cells are missing values.")
    assert "Repeated rows represent separate observations." in text
    assert first.usage.get("requests", 0) == 0
    replay = extract(SOURCE, options=options, out_dir=tmp_path / "cache")
    assert replay.cache_hit and replay.blocks == first.blocks and replay.markdown == first.markdown
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == GOLD["source_sha256"]
    first.validate_contract()


def test_unmerged_empty_zero_and_repeated_rows_stay_distinct():
    pytest.importorskip("pymupdf4llm")
    result = extract(SOURCE, options=ExtractOptions(pdf_backend="pymupdf", ocr="off", max_ai_requests=0))
    block = next(b for b in result.blocks if b.source.index == 1)
    text = result.markdown[block.start:block.end]
    assert "| B |  | 0 |" in text
    assert text.count("| C | ready | 1 |") == 2
    assert "<table>" not in text


def merged_table():
    return SimpleNamespace(
        bbox=(0, 0, 2, 2), header=SimpleNamespace(external=False),
        extract=lambda: [["<Readings & units>", None], ["", "0"]],
        rows=[SimpleNamespace(cells=[(0, 0, 2, 1), None]),
              SimpleNamespace(cells=[(0, 1, 1, 2), (1, 1, 2, 2)])],
    )


MARKDOWN = "Before\n\n| header |  |\n|---|---|\n|  | 0 |\n\nAfter"


def render(table):
    warnings = []
    text = native_tables(MARKDOWN, lambda count: None, warnings.append,
                         lambda: SimpleNamespace(tables=[table]))
    return text, warnings


def test_html_escapes_cell_text_without_losing_empty_cell_or_zero():
    text, warnings = render(merged_table())
    assert '<th colspan="2">&lt;Readings &amp; units&gt;</th>' in text
    assert "<td></td><td>0</td>" in text
    assert text.startswith("Before\n\n") and text.endswith("\n\nAfter")
    assert not warnings


def test_html_span_markup_cannot_mask_dropped_source_words():
    page = SimpleNamespace(get_text=lambda *a, **k: [(0, 0, 1, 1, "rowspan colspan", 0, 0)])
    markup = '<table><tr><th rowspan="2" colspan="2">0</th></tr></table>'
    assert missing_source_blocks(page, markup) == ["rowspan colspan"]


def test_escaped_cell_text_remains_source_text_for_omission_check():
    page = SimpleNamespace(get_text=lambda *a, **k: [(0, 0, 1, 1, "A < B & C", 0, 0)])
    assert not missing_source_blocks(page, '<table><tr><td>A &lt; B &amp; C</td></tr></table>')


def test_multiline_cell_text_preserves_line_breaks():
    table = merged_table()
    table.extract = lambda: [["Line one\r\nLine two", None], ["", "0"]]
    text, warnings = render(table)
    parsed = Cells()
    parsed.feed(text)
    assert parsed.rows[0] == [("Line one\nLine two", 1, 2)]
    assert not warnings


def test_external_merged_header_is_not_invented():
    table = merged_table()
    table.header.external = True
    text, warnings = render(table)
    assert text == MARKDOWN and warnings


def test_cell_budget_failure_is_not_treated_as_ambiguous_geometry():
    def limited(count):
        raise ValueError("cell budget exhausted")

    with pytest.raises(ValueError, match="cell budget"):
        native_tables(MARKDOWN, limited, lambda message: pytest.fail(message),
                      lambda: SimpleNamespace(tables=[merged_table()]))


@pytest.mark.parametrize("damage", ["unowned", "overlap", "covered_text", "nonfinite", "missing_geometry"])
def test_ambiguous_merged_geometry_preserves_original_markdown(damage):
    table = merged_table()
    if damage == "unowned":
        table.rows[0].cells[0] = (0, 0, 1, 1)
    elif damage == "overlap":
        table.rows[1].cells[0] = (0, 0, 1, 2)
    elif damage == "covered_text":
        table.extract = lambda: [["Header", "unowned text"], ["", "0"]]
    elif damage == "nonfinite":
        table.rows[0].cells[0] = (0, 0, float("nan"), 1)
    else:
        table.rows = []
    text, warnings = render(table)
    assert text == MARKDOWN
    assert warnings and "ambiguous" in warnings[0].lower()


def test_geometry_ambiguity_is_a_scoped_publication_hold(tmp_path, monkeypatch):
    pdf = pytest.importorskip("pymupdf")
    pytest.importorskip("pymupdf4llm")
    with pdf.open(SOURCE) as doc:
        doc.select([2])
        path = tmp_path / "merged.pdf"
        doc.save(path)
    from mdaddict.extract_offline import OfflineExtractor
    def ambiguous(markdown, check_cells, report, get_found_tables):
        # Keep the real converter's table discovery; inject uncertainty only at
        # mdaddict's geometry-to-Markdown boundary.
        return native_tables(markdown, check_cells, report, lambda: SimpleNamespace(tables=[]))

    monkeypatch.setattr("mdaddict.extract_offline.native_tables", ambiguous)
    result = OfflineExtractor(ExtractOptions(pdf_backend="pymupdf", ocr="off")).extract(path)
    issues = [i for i in result.issues if i.code == "pdf_table_structure_unresolved"]
    assert len(issues) == 1 and issues[0].block_ids == ["page:1"]
    assert issues[0].severity == "unresolved" and result.status == "partial"
    record = asdict(result)
    for issue in record["issues"]:
        issue["severity"] = "informational"
    restored = ExtractResult(**record)
    restored.refresh_status()
    assert restored.status == "partial"
