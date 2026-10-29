"""Explicit local-only extended readers; never construct MarkItDown's dispatcher.

Delegated Markdown has document-level provenance. It does not establish native
page, cell, or visual fidelity, and omitted content remains a blocking issue.
"""
from __future__ import annotations

from importlib import import_module, metadata
import io
import json
from pathlib import Path
import re

from .dependencies import MissingDependencyError
from .strategy import (ExtractOptions, ExtractResult, ExtractionIssue, SourceBlock,
                       SourceLocator, normalize, sha256_file)


MARKITDOWN_READERS = {
    ".xls": ("_xlsx_converter", "XlsConverter", "xls"),
    ".epub": ("_epub_converter", "EpubConverter", ""),
    ".ipynb": ("_ipynb_converter", "IpynbConverter", ""),
    ".msg": ("_outlook_msg_converter", "OutlookMsgConverter", "outlook"),
    ".rss": ("_rss_converter", "RssConverter", ""),
    ".atom": ("_rss_converter", "RssConverter", ""),
}
LEGACY_TYPES = frozenset({".doc", ".ppt", ".odt", ".rtf", ".org", ".adoc", ".asciidoc", ".tex", ".latex", ".opml", ".fb2", ".typ"})


def coarse_result(path: Path, markdown: str, backend: str, *, issues=(), metadata_extra=None):
    """Wrap delegated output without fabricating fine-grained source locations."""
    markdown = normalize(markdown)
    locator = SourceLocator("document", 1, "delegated whole document")
    blocks = [SourceBlock("document-1", "document", locator, 0, len(markdown))]
    notices = [ExtractionIssue("delegated_provenance_coarse",
        "Delegated output is located to the whole original document; internal layout and completeness are not certified.",
        locator, ["document-1"], "informational")]
    notices.extend(ExtractionIssue(code, message, locator, ["document-1"], "unresolved")
                   for code, message in issues)
    if not markdown.strip():
        notices.append(ExtractionIssue("delegated_content_empty",
            "The reader produced no body content; this is not a complete conversion.",
            locator, ["document-1"], "unresolved"))
    result = ExtractResult(sha256_file(path), markdown, path.name, backend,
        blocks=blocks, issues=notices, usage={"requests": 0},
        metadata={"delegated": {"backend": backend, "provenance": "document", "network": "none",
                                **(metadata_extra or {})}})
    result.refresh_status()
    return result


def _markitdown_reader(suffix):
    module, name, extra = MARKITDOWN_READERS[suffix]
    instruction = f"markitdown[{extra}]==0.1.9" if extra else "markitdown==0.1.9"
    try:
        version = metadata.version("markitdown")
        if version != "0.1.9":
            raise MissingDependencyError(f"Extended readers require {instruction}; installed version is {version}.")
        reader = getattr(import_module(f"markitdown.converters.{module}"), name)()
        stream_info = import_module("markitdown._stream_info").StreamInfo
    except (ImportError, metadata.PackageNotFoundError) as exc:
        raise MissingDependencyError(f"Install the optional extended reader with pip install '{instruction}'.") from exc
    return reader, stream_info


def _notebook(reader, stream_info, path, options):
    """Use the maintained cell converter, retaining declared code language and omissions."""
    notebook = json.loads(path.read_text(encoding=options.encoding))
    pieces, issues = [], []
    language = notebook.get("metadata", {}).get("language_info", {}).get("name", "")
    language = language or notebook.get("metadata", {}).get("kernelspec", {}).get("language", "")
    language = language if re.fullmatch(r"[A-Za-z0-9_+.-]{1,40}", language) else ""
    for cell in notebook.get("cells", []):
        # Convert one cell at a time so only its opening fence is changed;
        # literal fences inside source code must remain byte-for-byte content.
        data = json.dumps({"cells": [cell], "metadata": {}}).encode("utf-8")
        converted = reader.convert(io.BytesIO(data), stream_info(extension=".ipynb", charset="utf-8"))
        text = converted.markdown
        if cell.get("cell_type") == "code" and text.startswith("```python\n"):
            text = "```" + language + "\n" + text[len("```python\n"):]
        if cell.get("outputs") or cell.get("attachments"):
            issues.append(("notebook_outputs_omitted",
                "Saved notebook outputs or embedded attachments were not converted; inspect the original notebook."))
        if cell.get("cell_type") not in {"markdown", "code", "raw"}:
            issues.append(("notebook_cell_unsupported", "A notebook cell type was not converted."))
        pieces.append(text)
    return "\n\n".join(pieces), list(dict.fromkeys(issues))


def extract_extended(path: Path, options: ExtractOptions) -> ExtractResult:
    """Read supported extended files offline; missing capabilities fail explicitly."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".srt", ".vtt"}:
        from .subtitles import extract_subtitles
        return extract_subtitles(path, options)
    if suffix in {".zip", ".eml", ".p7s"}:
        from .containers import extract_container
        return extract_container(path, options)
    if suffix in LEGACY_TYPES:
        from .legacy import extract_legacy
        return extract_legacy(path, options)
    if suffix not in MARKITDOWN_READERS:
        raise ValueError(f"No offline extended reader for {suffix!r}")
    if suffix == ".epub":
        from .containers import check_zip_budget
        check_zip_budget(path, options)
    if suffix == ".xls":
        try:
            import xlrd
        except ImportError as exc:
            raise MissingDependencyError("Install mdaddict[extended] to read XLS files.") from exc
        workbook = xlrd.open_workbook(str(path), on_demand=True)
        try:
            cells = sum(workbook.sheet_by_index(index).nrows * workbook.sheet_by_index(index).ncols
                        for index in range(workbook.nsheets))
            if cells > options.max_cells:
                raise ValueError("XLS rectangular cell count exceeds max_cells")
        finally:
            workbook.release_resources()
    reader, stream_info = _markitdown_reader(suffix)
    issues = []
    try:
        if suffix == ".ipynb":
            markdown, issues = _notebook(reader, stream_info, path, options)
        else:
            with path.open("rb") as stream:
                markdown = reader.convert(stream, stream_info(extension=suffix, filename=path.name)).markdown
    except Exception as exc:
        if type(exc).__name__ == "MissingDependencyException":
            extra = MARKITDOWN_READERS[suffix][2]
            raise MissingDependencyError(f"Install pip install 'markitdown[{extra}]==0.1.9' for {suffix}.") from exc
        raise
    if suffix == ".msg" and not markdown.partition("## Content")[2].strip():
        issues.append(("mail_body_unavailable", "Only mail metadata was read; no plain-text body was available."))
    if suffix == ".msg":
        issues.append(("mail_attachments_unconverted",
            "This MSG reader does not enumerate attachments or alternative rich bodies; inspect the original message."))
    if suffix == ".epub":
        issues.append(("epub_visual_content_unverified",
            "EPUB spine text was converted; embedded images, media and non-spine material are not transcribed."))
    if suffix == ".xls":
        issues.append(("xls_cached_values_unverified",
            "XLS conversion reads cached cell values; formulas, drawings and workbook behavior are not preserved."))
    return coarse_result(path, markdown, "markitdown-0.1.9-" + suffix[1:], issues=issues)


def extract_web_snapshot(path, options, url):
    """Use only the maintained Wikipedia/Bing snapshot readers, without fetching."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if re.fullmatch(r"[a-z]{2,3}(?:\.m)?\.wikipedia\.org", host):
        module, name = "_wikipedia_converter", "WikipediaConverter"
    elif host == "www.bing.com" and parts.path == "/search":
        module, name = "_bing_serp_converter", "BingSerpConverter"
    else:
        return None
    # Reuse the same version/dependency guard as the other selected readers.
    _, stream_info = _markitdown_reader(".rss")
    reader = getattr(import_module("markitdown.converters." + module), name)()
    with path.open("rb") as stream:
        markdown = reader.convert(stream, stream_info(extension=".html", mimetype="text/html", url=url)).markdown
    return coarse_result(path, markdown, "markitdown-0.1.9-" + name,
        issues=[("web_snapshot_scope", "Only the selected static page content was converted; dynamic and linked content were not fetched.")])
