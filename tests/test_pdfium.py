"""Permissive PDF behavior must execute without importing the legacy stack."""
import builtins
import io

import pytest

pytest.importorskip("pypdfium2")
pypdf = pytest.importorskip("pypdf")

from mdaddict import ExtractOptions, MissingDependencyError, extract


@pytest.fixture(autouse=True)
def no_legacy_imports(monkeypatch):
    original = builtins.__import__

    def checked(name, *args, **kwargs):
        if name.split(".")[0] in {"pymupdf", "pymupdf4llm"}:
            pytest.fail("PDFium attempted to import the optional PyMuPDF stack")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked)


@pytest.fixture
def pdf_source(tmp_path):
    def write(content):
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=400, height=240)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(content.encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        path = tmp_path / "source.pdf"
        writer.write(path)
        writer.close()
        return path
    return write


PROSE = "BT /F1 12 Tf 40 200 Td (Preserve the original measurements and conditions.) Tj ET\n"


def convert(source, **options):
    return extract(source, options=ExtractOptions(pdf_backend="pdfium", ocr="off", **options))


def test_plain_text_and_cache_spans_without_legacy_imports(pdf_source, tmp_path):
    path = pdf_source(PROSE)
    result = extract(path, options=ExtractOptions(pdf_backend="pdfium", ocr="off"), out_dir=tmp_path / "out")
    assert "original measurements" in result.markdown and result.status == "success"
    result.validate_contract()
    cached = extract(path, options=ExtractOptions(pdf_backend="pdfium", ocr="off"), out_dir=tmp_path / "out")
    assert cached.cache_hit and cached.blocks == result.blocks


@pytest.mark.parametrize("content", [
    "BT /F1 12 Tf 40 120 Td (x =) Tj 40 9 Td (1) Tj 0 -24 Td (2) Tj ET 79 123 m 96 123 l S",
    "40 80 m 300 80 l 300 150 l 40 150 l h S 150 80 m 150 150 l S",
    "BT /F1 12 Tf 40 120 Td (E = mc) Tj /F1 8 Tf 2 6 Td (2) Tj ET",
])
def test_uninterpreted_math_or_vector_structure_keeps_a_hold(pdf_source, content):
    result = convert(pdf_source(PROSE + content))
    assert result.status == "partial" and result.review_status == "needs_review"
    issues = [issue for issue in result.issues if issue.severity == "unresolved"]
    assert issues and all(issue.block_ids == ["page:1"] for issue in issues)
    result.validate_contract()


def test_failed_object_inspection_keeps_a_hold(pdf_source, monkeypatch):
    import pypdfium2
    def broken(*args, **kwargs):
        raise pypdfium2.PdfiumError("object enumeration failed")
    monkeypatch.setattr(pypdfium2.PdfPage, "get_objects", broken)
    result = convert(pdf_source(PROSE))
    assert result.status == "partial"
    assert any(issue.code == "pdf_layout_unresolved" for issue in result.issues)


def test_pdfium_ai_repair_is_an_explicit_capability_error(pdf_source):
    class Provider:
        name, model_id = "test-double", "no-model"
        settings, cache_identity = {}, {"revision": "no-calls"}
        def call(self, request):
            pytest.fail("No AI requests authorized")
    with pytest.raises(MissingDependencyError, match="pdf_backend='pymupdf'"):
        extract(pdf_source(PROSE), ai_provider=Provider(),
                options=ExtractOptions(pdf_backend="pdfium", ocr="off", max_ai_requests=0))


def test_pdfium_rendering_caps_longest_side():
    from PIL import Image
    from mdaddict.pdf_pdfium import _render_png
    scales = []
    class Bitmap:
        def to_pil(self):
            return Image.new("RGB", (2, 2))
        def close(self):
            pass
    class Page:
        def get_size(self):
            return 10_000, 20_000
        def render(self, scale):
            scales.append(scale)
            return Bitmap()
    with Image.open(io.BytesIO(_render_png(Page(), 300))) as image:
        assert image.format == "PNG"
    assert max(Page().get_size()) * scales[0] <= 2400


def test_math_hold_survives_cache_and_severity_downgrade(pdf_source, tmp_path):
    from dataclasses import asdict
    from mdaddict import ExtractResult
    path = pdf_source(PROSE + "BT /F1 12 Tf 40 120 Td (x = 2) Tj ET")
    options = ExtractOptions(pdf_backend="pdfium", ocr="off")
    first = extract(path, options=options, out_dir=tmp_path / "out")
    cached = extract(path, options=options, out_dir=tmp_path / "out")
    assert first.status == cached.status == "partial" and cached.cache_hit
    record = asdict(cached)
    for issue in record["issues"]:
        issue["severity"] = "informational"
    restored = ExtractResult(**record)
    restored.refresh_status()
    assert restored.status == "partial" and restored.review_status == "needs_review"
