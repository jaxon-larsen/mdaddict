"""Installed-library behavior, independent of the education application."""
import importlib.resources
import json
import socket

import pytest

from mdaddict import ExtractOptions, ExtractResult, MissingDependencyError, extract, to_markdown


def test_markdown_and_structured_result_share_one_pipeline(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Source\n\n$x^2$ costs $3.\n", encoding="utf-8")
    result = extract(str(source))
    assert isinstance(result, ExtractResult)
    assert to_markdown(source) == result.markdown == source.read_text(encoding="utf-8")
    result.validate_contract()
    assert result.blocks and result.sha256
    assert sorted(p.name for p in tmp_path.iterdir()) == ["notes.md"]


def test_environment_cannot_enable_a_provider(tmp_path, monkeypatch):
    source = tmp_path / "source.csv"
    source.write_text("name,value\nA,2\n", encoding="utf-8")
    monkeypatch.setenv("EXTRACT_STRATEGY", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("network attempted"))
    result = extract(source)
    assert result.metadata["strategy"] == "offline"
    assert result.usage.get("requests", 0) == 0
    assert "| A | 2 |" in result.markdown


def test_schema_is_an_installed_resource():
    schema = json.loads(importlib.resources.files("mdaddict").joinpath("schema/extract-result.schema.json").read_text())
    assert schema["properties"]["schema_version"]["const"] == "1.0"


def test_cache_replay_and_corruption_are_safe(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Keep all source content.\n", encoding="utf-8")
    output = tmp_path / "output"
    first = extract(source, out_dir=output)
    assert not first.cache_hit
    assert extract(source, out_dir=output).cache_hit
    cached = next(output.rglob("*.md"))
    cached.write_text("Different content", encoding="utf-8")
    repaired = extract(source, out_dir=output)
    assert not repaired.cache_hit and repaired.markdown == first.markdown
    assert source.read_text(encoding="utf-8") == first.markdown


def test_missing_format_dependency_has_an_install_instruction(tmp_path, monkeypatch):
    import mdaddict.dependencies as dependencies
    source = tmp_path / "source.pdf"
    source.write_bytes(b"not parsed when the dependency is missing")
    real = dependencies.find_spec
    monkeypatch.setattr(dependencies, "find_spec", lambda name: None if name in {"pymupdf", "pypdfium2"} else real(name))
    with pytest.raises(MissingDependencyError, match=r"mdaddict\[pdf\]"):
        extract(source)


def test_options_keep_offline_ocr_automatic():
    assert ExtractOptions().ocr == "auto"


def test_nested_vendor_change_invalidates_cached_conversion(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module("mdaddict.extract")
    package = tmp_path / "implementation"
    (package / "_vendor").mkdir(parents=True)
    entry = package / "extract.py"
    entry.write_text("# same integration", encoding="utf-8")
    parser = package / "_vendor" / "parser.py"
    parser.write_text("# parser revision 1", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", str(entry))
    source = tmp_path / "source.txt"
    source.write_text("Keep source.", encoding="utf-8")
    first = extract(source, out_dir=tmp_path / "out")
    assert extract(source, out_dir=tmp_path / "out").cache_hit
    parser.write_text("# parser revision 2", encoding="utf-8")
    second = extract(source, out_dir=tmp_path / "out")
    assert not second.cache_hit and second.cache_key != first.cache_key
    assert second.markdown == first.markdown
