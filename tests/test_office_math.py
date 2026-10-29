"""Vendored equation conversion requires no Pandoc and preserves source anchors."""
import subprocess
import importlib
import xml.etree.ElementTree as ET

import pytest

from mdaddict import ExtractOptions, extract


def test_pptx_equation_needs_no_external_process(tmp_path, monkeypatch):
    pptx = pytest.importorskip("pptx")
    etree = pytest.importorskip("lxml.etree")
    from mdaddict.extract_offline import OfflineExtractor
    deck = pptx.Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    paragraph = slide.shapes.add_textbox(0, 0, 10000, 10000).text_frame.paragraphs[0]
    paragraph.text = "Before "
    paragraph._p.append(etree.fromstring(b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:oMath>'))
    paragraph.add_run().text = " after."
    monkeypatch.setattr(importlib.import_module("mdaddict.extract"), "dependency_versions", lambda: {})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("external process for native Office math"))
    expressions = OfflineExtractor(ExtractOptions(ocr="off"))._office_math(deck)
    assert list(expressions.values()) == ["$x^{2}$"]
    path = tmp_path / "equation.pptx"
    deck.save(path)
    result = extract(path, options=ExtractOptions(ocr="off"))
    assert "Before $x^{2}$ after." in result.markdown
    result.validate_contract()
    assert any("$x^{2}$" in result.markdown[b.start:b.end] for b in result.blocks)


def test_unknown_math_content_is_not_silently_discarded():
    from mdaddict.office_math import convert_equation
    node = ET.fromstring(b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:unknown><m:r><m:t>x</m:t></m:r></m:unknown></m:oMath>')
    with pytest.raises(ValueError, match="Unsupported"):
        convert_equation(node)


@pytest.mark.parametrize("source, expected", [("x\u00a0", "$x$ "), ("$\u00a0", r"$\$$ "), ("x", "$x$")])
def test_math_boundary_spacing_is_source_based(source, expected):
    from mdaddict.office_math import convert_equation
    node = ET.Element("{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath")
    run = ET.SubElement(node, "{http://schemas.openxmlformats.org/officeDocument/2006/math}r")
    ET.SubElement(run, "{http://schemas.openxmlformats.org/officeDocument/2006/math}t").text = source
    assert convert_equation(node) == expected
    assert [text.text for text in node.iter("{http://schemas.openxmlformats.org/officeDocument/2006/math}t")] == [source]


def run(text):
    return "<m:r><m:t>" + text + "</m:t></m:r>"


@pytest.mark.parametrize("fragment, expected", [
    ("<m:f><m:num>" + run("x+1") + "</m:num><m:den>" + run("2") + "</m:den></m:f>", r"\frac{x+1}{2}"),
    ('<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>' + run("x+1") + "</m:e></m:rad>", r"\sqrt{x+1}"),
    ("<m:sSubSup><m:e>" + run("x") + "</m:e><m:sub>" + run("i") + "</m:sub><m:sup>" + run("2") + "</m:sup></m:sSubSup>", "x_{i}^{2}"),
    ("<m:m><m:mr><m:e>" + run("a") + "</m:e><m:e>" + run("b") + "</m:e></m:mr><m:mr><m:e>" + run("c") + "</m:e><m:e>" + run("d") + "</m:e></m:mr></m:m>", r"\begin{matrix} a & b \\ c & d \end{matrix}"),
])
def test_source_defined_equation_controls(fragment, expected):
    from mdaddict.office_math import convert_equation
    node = ET.fromstring('<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">' + fragment + '</m:oMath>')
    assert convert_equation(node) == "$" + expected + "$"


def test_unknown_nested_content_and_foreign_namespaces_are_rejected():
    from mdaddict.office_math import convert_equation
    for content in ('<m:r><m:unknown>lost</m:unknown></m:r>', '<r xmlns="urn:foreign"><t>x</t></r>'):
        node = ET.fromstring('<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">' + content + '</m:oMath>')
        with pytest.raises(ValueError, match="Unsupported"):
            convert_equation(node)


def test_vendor_source_and_license_are_auditable_installed_resources():
    from importlib.resources import files
    import hashlib
    vendor = files("mdaddict._vendor")
    assert hashlib.sha256(vendor.joinpath("omml2latex.py").read_bytes()).hexdigest() == "1ea42deb02b417573872a448d836c283e964a963a4d546a627c1761b1ecf26f1"
    assert hashlib.sha256(vendor.joinpath("licenses/omml2latex-LICENSE").read_bytes()).hexdigest() == "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
    assert "Copyright 2026 INSEONG LEE" in vendor.joinpath("NOTICE").read_text(encoding="utf-8")
