"""Packaging compatibility snapshots, not independent fidelity certification."""
from dataclasses import asdict
from copy import deepcopy
from importlib.util import find_spec
import json
from pathlib import Path
import shutil

import pytest

from mdaddict import ExtractOptions, extract


ROOT = Path(__file__).parent / "fixtures"
CASES = json.loads((ROOT / "packaging-baseline.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda row: row["path"] or row["suffix"])
def test_pre_migration_output_and_source_spans_with_reviewed_math_spacing(case, tmp_path):
    # The captured PDF baseline targets the legacy backend. PDFium's own source
    # controls in test_pdfium.py explicitly select it in a permissive-only install.
    required = {".pdf": "pymupdf4llm", ".pptx": "pptx", ".docx": "lxml"}.get(case["suffix"])
    if required and find_spec(required) is None:
        pytest.skip("Optional format extra is absent")
    needs_pandoc = case["suffix"] == ".docx" or (case["suffix"] == ".html" and find_spec("markdownify") is None)
    if needs_pandoc and not shutil.which("pandoc"):
        pytest.skip("Pandoc is absent")
    if case["path"]:
        source = ROOT / case["path"]
    else:
        source = tmp_path / ("input" + case["suffix"])
        source.write_text(case["input"], encoding="utf-8")
    result = asdict(extract(source, options=ExtractOptions(ocr="off")))
    expected = deepcopy(case["result"])
    if result["assets"] or case["path"] == "algebra.pptx":
        # Approved additive asset contract: replace only legacy figure markers,
        # preserving every teaching character and shifting exact source spans.
        edits = [(r"y = \frac{x + 1}{2}", r"y=\frac{x+1}{2}"),
                 (r"r = \sqrt{x^{2} + 1}", r"r=\sqrt{x^{2}+1}")]
        if case["path"] != "algebra.pptx":
            edits = []
        if result["assets"]:
            expected["status"] = "partial"
            expected["review_status"] = "needs_review"
        for asset in result["assets"]:
            block = next(b for b in expected["blocks"] if b["id"] == asset["block_ids"][0])
            before = expected["markdown"][block["start"]:block["end"]].strip()
            assert before.startswith("<!-- fig:") and before.endswith("-->")
            edits.append((before, f"![{asset['description']}](asset:{asset['asset_id']})"))
            expected["issues"].append({"code": "asset_context_unresolved",
                "message": "Visual meaning requires comparison against the original before assessed practice",
                "source": asset["locator"], "block_ids": asset["block_ids"], "severity": "unresolved"})
        original = expected["markdown"]
        offsets = []
        for before, after in edits:
            assert original.count(before) == 1
            offsets.append((original.index(before) + len(before), len(after) - len(before)))
            expected["markdown"] = expected["markdown"].replace(before, after)
        for block in expected["blocks"]:
            for boundary in ("start", "end"):
                block[boundary] += sum(delta for end, delta in offsets if end <= block[boundary])
    assert {key: result[key] for key in expected} == expected


def test_xlsx_remains_available_via_office_extra(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "sheet.xlsx"
    book = openpyxl.Workbook()
    book.active.append(["Value", "Formula"])
    book.active.append([3, "=A2*2"])
    book.save(path)
    book.close()
    result = extract(path)
    assert "=A2*2" in result.markdown and result.pages == 1
    result.validate_contract()


def test_local_ocr_when_runtime_is_installed(tmp_path):
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract is absent")
    image = pytest.importorskip("PIL.Image")
    draw = pytest.importorskip("PIL.ImageDraw")
    font = pytest.importorskip("PIL.ImageFont")
    path = tmp_path / "scan.png"
    canvas = image.new("RGB", (800, 180), "white")
    draw.Draw(canvas).text((40, 40), "SAMPLE TEXT", fill="black", font=font.load_default(size=48))
    canvas.save(path)
    result = extract(path)
    assert "SAMPLE" in result.markdown.upper()
    assert result.usage.get("requests", 0) == 0
    result.validate_contract()
