"""Authored PDFs isolate baseline order from glyph ink-box height.

Expectations come from the authored text/layout, never converter output or a
private source. No model, font download, or additional format dependency.
"""
from dataclasses import asdict
import hashlib

import pytest

from mdaddict import ExtractOptions, extract


def decimal_pdf(path, *, scale=1, offset=0, value="0.01"):
    pdf = pytest.importorskip("pymupdf")
    pytest.importorskip("pymupdf4llm")
    with pdf.open() as doc:
        page = doc.new_page(width=600 * scale, height=320 * scale)
        def point(x, y):
            return ((x + offset) * scale, y * scale)
        for r in range(2):
            for c in range(2):
                page.draw_rect(pdf.Rect(*point(40 + 210 * c, 80 + 50 * r),
                                        *point(250 + 210 * c, 130 + 50 * r)))
        page.insert_text(point(50, 65), "Independent numeric observations", fontsize=11 * scale)
        page.insert_text(point(50, 110), "Interval", fontsize=12 * scale)
        page.insert_text(point(260, 110), "Measurement", fontsize=12 * scale)
        page.insert_text(point(50, 160), "Observed", fontsize=12 * scale)
        x = 260 + offset
        for char in value:
            # Same baseline, different glyph height; dots must not move to a
            # separate line or be appended at the end of the numeric value.
            size = (5 if char == "." else 12) * scale
            page.insert_text((x * scale, 160 * scale), char, fontsize=size, fontname="tiro")
            x += pdf.get_text_length(char, fontname="tiro", fontsize=size) / scale
        page.insert_text(point(50, 215), "The next paragraph is independent.", fontsize=11 * scale)
        doc.save(path, no_new_id=True)
    return path


@pytest.mark.parametrize("scale,offset,value", [(1, 0, "0.01"), (1.6, 12, "-8.125"), (.8, 30, "42.75%")])
def test_mixed_font_decimal_stays_on_its_authored_baseline(tmp_path, scale, offset, value):
    path = decimal_pdf(tmp_path / "values.pdf", scale=scale, offset=offset, value=value)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    options = ExtractOptions(pdf_backend="pymupdf", ocr="off", max_ai_requests=0)
    result = extract(path, options=options, out_dir=tmp_path / "cache")
    assert f"| Observed | {value} |" in result.markdown
    assert "The next paragraph is independent." in result.markdown
    assert result.sha256 == digest and hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert result.usage.get("requests", 0) == 0
    result.validate_contract()
    replay = extract(path, options=options, out_dir=tmp_path / "cache")
    assert replay.cache_hit and replay.markdown == result.markdown and replay.blocks == result.blocks


def test_unresolved_internal_columns_are_held_without_inventing_cells(tmp_path):
    pdf = pytest.importorskip("pymupdf")
    pytest.importorskip("pymupdf4llm")
    path = tmp_path / "packed.pdf"
    with pdf.open() as doc:
        page = doc.new_page(width=500, height=320)
        for r in range(2):
            for c in range(2):
                page.draw_rect(pdf.Rect(40 + 190 * c, 70 + 70 * r, 230 + 190 * c, 140 + 70 * r))
        for point, text in [((50, 110), "Groups"), ((240, 110), "Observed values"),
                            ((50, 165), "First"), ((50, 190), "Second"),
                            ((245, 165), "9"), ((315, 165), "0"), ((385, 165), "7"),
                            ((245, 190), "2"), ((315, 190), "2"), ((385, 190), "1")]:
            page.insert_text(point, text, fontsize=11)
        doc.save(path, no_new_id=True)
    result = extract(path, options=ExtractOptions(pdf_backend="pymupdf", ocr="off", max_ai_requests=0))
    assert "9 0 7<br>2 2 1" in result.markdown
    issues = [i for i in result.issues if i.code == "pdf_table_structure_unresolved"]
    assert issues and all(i.severity == "unresolved" and i.block_ids == ["page:1"] for i in issues)
    record = asdict(result)
    for issue in record["issues"]:
        issue["severity"] = "informational"
    from mdaddict import ExtractResult
    restored = ExtractResult(**record)
    restored.refresh_status()
    assert restored.status == "partial"


def glyphs(text, *, y=20, x=10):
    # Independent source positions: deliberately exaggerated ink heights are
    # not line membership. Origins, not the ink-box top, identify the baseline.
    return [{"c": c, "origin": (x + i * 5, y), "bbox": (x + i * 5, y - (2 if c == '.' else 8), x + i * 5 + 5, y + 2)}
            for i, c in enumerate(text)]


def cell_rows(chars, rows, *, direction=(1.0, 0.0), size=10):
    from types import SimpleNamespace
    from mdaddict.pdf_cell_text import native_cell_rows
    table = SimpleNamespace(bbox=(0, 0, 100, 100), rows=[SimpleNamespace(cells=[(0, 0, 100, 100)])])
    raw = {"blocks": [{"lines": [{"dir": direction, "spans": [{"size": size, "chars": chars}]}]}]}
    return native_cell_rows(table, rows, raw)


def test_punctuation_and_comparison_signs_follow_source_baselines_not_text_order():
    chars = glyphs('0.01≤p')
    # Drawing order is not reading order either.
    assert cell_rows(list(reversed(chars)), [['001≤p\n.']]) == ([['0.01≤p']], False)
    assert cell_rows(glyphs('001'), [['001']]) == ([['001']], False)  # no inserted decimal
    assert cell_rows(glyphs('0.01'), [['0.01']]) == ([['0.01']], False)


@pytest.mark.parametrize('damage', ['raised', 'rotated', 'overlap', 'boundary', 'baseline_border', 'rtl', 'missing', 'nonfinite'])
def test_uncertain_cell_text_is_not_reordered(damage):
    from mdaddict.pdf_tables import AmbiguousTable
    chars, direction, rows = glyphs('x2'), (1.0, 0.0), [['x2']]
    if damage == 'raised':
        chars[1]['origin'] = (15, 17)
    elif damage == 'rotated':
        direction = (0.0, 1.0)
    elif damage == 'overlap':
        chars[1]['origin'] = chars[0]['origin']
        chars[1]['bbox'] = chars[0]['bbox']
    elif damage == 'boundary':
        chars[1]['bbox'] = (15, 12, 105, 22)
    elif damage == 'baseline_border':
        chars[1]['origin'] = (15, 0)
    elif damage == 'rtl':
        chars[1]['c'] = 'א'
    elif damage == 'missing':
        rows = [['x2?']]
    else:
        chars[1]['bbox'] = (15, 12, float('nan'), 22)
    with pytest.raises(AmbiguousTable):
        cell_rows(chars, rows, direction=direction)


def test_wrapped_text_and_recorded_empty_space_keep_existing_rendering():
    chars = glyphs('wrapped') + glyphs('text', y=34)
    assert cell_rows(chars, [['wrapped\ntext']]) == ([['wrapped\ntext']], False)
    assert cell_rows([], [['']]) == ([['']], False)


def test_parallel_multiline_cells_require_review_without_becoming_invented_rows():
    from types import SimpleNamespace
    from mdaddict.pdf_cell_text import native_cell_rows
    table = SimpleNamespace(bbox=(0, 0, 200, 100), rows=[SimpleNamespace(cells=[(0, 0, 100, 100), (100, 0, 200, 100)])])
    chars = glyphs('First') + glyphs('Second', y=34) + glyphs('7', x=110) + glyphs('0', x=110, y=34)
    raw = {'blocks': [{'lines': [{'dir': (1.0, 0.0), 'spans': [{'size': 10, 'chars': chars}]}]}]}
    rows = [['First\nSecond', '7\n0']]
    assert native_cell_rows(table, rows, raw) == (rows, True)
    # Different wrapping does not establish aligned observation bands.
    chars[-1]['origin'] = (110, 50)
    assert native_cell_rows(table, rows, raw) == (rows, False)


@pytest.mark.parametrize('source,native,expected', [
    ('Before Treatment', 'BeforeTreatment', 'Before Treatment'),
    ('Image and Text Embeddings', 'ImageandTextEmbeddings', 'Image and Text Embeddings'),
    ('café labels', 'cafélabels', 'café labels'),
    ('1 000', '1000', '1 000'),
    ('alpha beta', 'alpha\t beta', 'alpha\t beta'),
    ('alpha', 'al pha', 'alpha'),
    ('identifier', 'identifier', 'identifier'),
])
def test_explicit_source_spaces_survive_without_reformatting_existing_whitespace(source, native, expected):
    # Widen this synthetic cell via a smaller advance, independently of font
    # metrics. Only an encoded source separator authorizes the added boundary.
    chars = glyphs(source)
    for i, char in enumerate(chars):
        char['origin'] = (5 + i * 3, 20)
        char['bbox'] = (5 + i * 3, 12, 8 + i * 3, 22)
    assert cell_rows(chars, [[native]]) == ([[expected]], False)


def test_geometric_gaps_alone_do_not_split_identifiers_or_rewrite_wrapping():
    chars = glyphs('AB')
    chars[1]['origin'] = (50, 20)
    chars[1]['bbox'] = (50, 12, 55, 22)
    assert cell_rows(chars, [['AB']]) == ([['AB']], False)
    assert cell_rows(chars, [['A B']]) == ([['A B']], False)


def test_separate_source_lines_do_not_authorize_removing_a_word_boundary():
    from types import SimpleNamespace
    from mdaddict.pdf_cell_text import native_cell_rows
    table = SimpleNamespace(bbox=(0, 0, 100, 100), rows=[SimpleNamespace(cells=[(0, 0, 100, 100)])])
    # Independently drawn fragments can meet spatially without representing a
    # single word. Lack of an encoded space across source runs is not proof.
    raw = {'blocks': [{'lines': [
        {'dir': (1.0, 0.0), 'spans': [{'size': 10, 'chars': glyphs('A')}]},
        {'dir': (1.0, 0.0), 'spans': [{'size': 10, 'chars': glyphs('B', x=15)}]},
    ]}]}
    assert native_cell_rows(table, [['A B']], raw) == ([['A B']], False)


def test_encoded_spaces_cross_font_spans_without_crossing_source_cells():
    from types import SimpleNamespace
    from mdaddict.pdf_cell_text import native_cell_rows
    table = SimpleNamespace(bbox=(0, 0, 100, 100), rows=[SimpleNamespace(cells=[(0, 0, 50, 100), (50, 0, 100, 100)])])
    raw = {'blocks': [{'lines': [{'dir': (1.0, 0.0), 'spans': [
        {'size': 10, 'chars': glyphs('A ')}, {'size': 10, 'chars': glyphs('B', x=20)},
        {'size': 10, 'chars': glyphs(' C', x=55)},
    ]}]}]}
    assert native_cell_rows(table, [['AB', 'C']], raw) == ([['A B', 'C']], False)


@pytest.mark.parametrize('font,scale', [('tiro', 1), ('helv', .75), ('tiro', 1.6)])
def test_authored_word_boundaries_and_unicode_survive_real_pdf_cache(tmp_path, font, scale):
    pdf = pytest.importorskip('pymupdf')
    pytest.importorskip('pymupdf4llm')
    path = tmp_path / 'source-words.pdf'
    labels = [('Condition', 'Description'), ('A', 'Before Treatment'), ('B', 'café labels')]
    with pdf.open() as doc:
        page = doc.new_page(width=500 * scale, height=300 * scale)
        for r, values in enumerate(labels):
            for c, text in enumerate(values):
                left, top = (40 + 200 * c) * scale, (80 + 40 * r) * scale
                page.draw_rect(pdf.Rect(left, top, left + 200 * scale, top + 40 * scale))
                page.insert_text((left + 8 * scale, top + 24 * scale), text, fontsize=11 * scale, fontname=font)
        doc.save(path, no_new_id=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    options = ExtractOptions(pdf_backend='pymupdf', ocr='off', max_ai_requests=0)
    result = extract(path, options=options, out_dir=tmp_path / 'cache')
    assert '| Condition | Description |' in result.markdown
    assert '| A | Before Treatment |' in result.markdown
    assert '| B | café labels |' in result.markdown
    assert result.sha256 == digest and hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert result.usage.get('requests', 0) == 0
    result.validate_contract()
    replay = extract(path, options=options, out_dir=tmp_path / 'cache')
    assert replay.cache_hit and replay.markdown == result.markdown and replay.blocks == result.blocks
