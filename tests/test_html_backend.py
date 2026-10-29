"""Offline HTML adapters retain content and use Pandoc only for complex markup."""
import socket
import subprocess
import importlib

import pytest

from mdaddict import ExtractOptions, extract


@pytest.fixture
def html_source(tmp_path):
    def write(text):
        path = tmp_path / "source.html"
        path.write_text(text, encoding="utf-8")
        return path
    return write


def test_simple_html_uses_markdownify_without_external_tools(html_source, monkeypatch):
    pytest.importorskip("markdownify")
    monkeypatch.setattr(importlib.import_module("mdaddict.extract"), "dependency_versions", lambda: {})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("external process for ordinary HTML"))
    source = html_source('<h1>Title</h1><p>Keep <b>both</b> values: λ and −3.</p><p>Keep units.</p><p>Keep units.</p><script>discard_script()</script>')
    result = extract(source, options=ExtractOptions(ocr="off"))
    assert result.extractor == "offline:markdownify"
    assert "# Title" in result.markdown and "**both**" in result.markdown
    assert "λ and −3" in result.markdown and result.markdown.count("Keep units.") == 2
    assert "discard_script" not in result.markdown
    result.validate_contract()


def test_html_image_is_an_unresolved_marker_and_never_fetched(html_source, monkeypatch):
    pytest.importorskip("markdownify")
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("network fetch"))
    result = extract(html_source('<p>Keep caption.</p><img src="https://invalid.example/plot.png" alt="Calibration plot">'))
    assert "Calibration plot" in result.markdown and "<!-- fig:" in result.markdown
    assert result.issues and result.usage.get("requests", 0) == 0


def test_html_simple_table_preserves_empty_and_repeated_cells(html_source):
    pytest.importorskip("markdownify")
    result = extract(html_source('<table><tr><th>A</th><th>B</th></tr><tr><td>0</td><td>0</td></tr><tr><td>1</td><td></td></tr></table>'))
    assert "| 0 | 0 |" in result.markdown and "| 1 |  |" in result.markdown


@pytest.mark.parametrize("markup", [
    '<table><tr><td colspan="2">Combined</td></tr></table>',
    '<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>',
    '<p>$x_1 + x_2$</p>',
    '<pre>before\n```\nafter</pre>',
    '<table><tr><td><code>a|b</code></td></tr></table>',
])
def test_complex_html_uses_existing_fidelity_path(html_source, monkeypatch, markup):
    pytest.importorskip("markdownify")
    from mdaddict.extract_offline import OfflineExtractor
    calls = []
    def fallback(self, path):
        calls.append(path)
        return "Complex content retained"
    monkeypatch.setattr(OfflineExtractor, "_pandoc", fallback)
    result = extract(html_source(markup))
    assert calls and result.extractor == "offline:pandoc"
    assert "Complex content retained" in result.markdown


def test_html_without_optional_library_keeps_pandoc_compatibility(html_source, monkeypatch):
    import mdaddict.html_native as html
    from mdaddict.extract_offline import OfflineExtractor
    monkeypatch.setattr(html, "find_spec", lambda name: None)
    monkeypatch.setattr(OfflineExtractor, "_pandoc", lambda self, path: "Existing installation")
    result = extract(html_source("<p>Existing installation</p>"))
    assert result.extractor == "offline:pandoc"


def test_literal_markdown_syntax_stays_literal(html_source):
    pytest.importorskip("markdownify")
    result = extract(html_source('<p>[literal] and `literal`.</p><table><tr><th>Value</th></tr><tr><td>a|b</td></tr></table>'))
    assert r"\[literal\]" in result.markdown
    assert r"\`literal\`" in result.markdown
    assert r"a\|b" in result.markdown

