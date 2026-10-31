"""Authored reader controls; optional local tools never download or call models."""
import shutil
import subprocess

import pytest

from mdaddict import ExtractOptions, MissingDependencyError, extract


@pytest.mark.parametrize("suffix,source", [
    (".org", "* Source\nQualified words\n"),
    (".rtf", r"{\rtf1\ansi Qualified words}"),
    (".tex", r"\documentclass{article}\begin{document}Qualified words\end{document}"),
    (".adoc", "= Source\n\nQualified words\n"),
    (".typ", "= Source\nQualified words\n"),
    (".opml", '<opml version="2.0"><head/><body><outline text="Qualified words"/></body></opml>'),
    (".fb2", '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"><description/><body><section><p>Qualified words</p></section></body></FictionBook>'),
])
def test_installed_pandoc_readers(tmp_path, suffix, source):
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        pytest.skip("Pandoc is absent")
    if suffix == ".adoc" and "asciidoc" not in subprocess.run([pandoc, "--list-input-formats"], capture_output=True, text=True, check=True).stdout.split():
        pytest.skip("Installed Pandoc has no asciidoc reader")
    path = tmp_path / ("source" + suffix)
    path.write_text(source, encoding="utf-8")
    result = extract(path, options=ExtractOptions(ocr="off"))
    assert "Qualified words" in result.markdown
    assert result.status == "partial"
    assert any(issue.code == "legacy_layout_unverified" for issue in result.issues)


def test_legacy_doc_and_xls_local_bridges(tmp_path):
    if shutil.which("pandoc") is None:
        pytest.skip("Pandoc is absent")
    pytest.importorskip("markitdown")
    pytest.importorskip("openpyxl")
    from mdaddict.legacy import _soffice
    from openpyxl import Workbook
    try:
        soffice = _soffice()
    except MissingDependencyError:
        pytest.skip("LibreOffice is absent")
    source = tmp_path / "word.rtf"
    source.write_text(r"{\rtf1\ansi Qualified words}")
    book = Workbook()
    book.active.append(["Name", "Value"])
    book.active.append(["Qualified words", 2])
    book.save(tmp_path / "sheet.xlsx")
    book.close()
    for input_path, extension in ((source, "doc"), (tmp_path / "sheet.xlsx", "xls")):
        subprocess.run([soffice, "-env:UserInstallation=" + (tmp_path / "profile").as_uri(),
            "--headless", "--safe-mode", "--convert-to", extension, "--outdir", str(tmp_path), str(input_path)],
            capture_output=True, timeout=60, check=True)
        converted = input_path.with_suffix("." + extension)
        assert converted.is_file()
        result = extract(converted, options=ExtractOptions(ocr="off"))
        assert "Qualified words" in result.markdown and result.status == "partial"
