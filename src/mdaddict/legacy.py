"""Local Pandoc/LibreOffice bridges with original-file provenance.

The website must run document-conversion subprocesses in its network-isolated
worker. No URL, remote resource-fetch option, macro, or notebook is executed by
this adapter. Converted-office locators refer to the intermediate representation.
"""
from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .delegated import coarse_result
from .dependencies import MissingDependencyError
from .strategy import ExtractOptions, ExtractionIssue, SourceLocator, sha256_file

PANDOC_READERS = {".odt": "odt", ".rtf": "rtf", ".org": "org", ".adoc": "asciidoc",
    ".asciidoc": "asciidoc", ".tex": "latex", ".latex": "latex", ".opml": "opml",
    ".fb2": "fb2", ".typ": "typst"}


def _soffice():
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable:
        return executable
    for root in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", "")):
        candidate = Path(root) / "LibreOffice/program/soffice.exe"
        if root and candidate.is_file():
            return str(candidate)
    raise MissingDependencyError("Install LibreOffice and place soffice/libreoffice on PATH to read legacy DOC/PPT files.")


def extract_legacy(path: Path, options: ExtractOptions):
    suffix = path.suffix.lower()
    if suffix in PANDOC_READERS:
        executable = shutil.which("pandoc")
        if not executable:
            raise MissingDependencyError(f"Install Pandoc and place pandoc on PATH to read {suffix} files.")
        if suffix == ".odt":
            from .containers import check_zip_budget
            check_zip_budget(path, options)
        readers = subprocess.run([executable, "--list-input-formats"], capture_output=True,
            encoding="utf-8", timeout=options.timeout, check=True).stdout.splitlines()
        reader = PANDOC_READERS[suffix]
        if reader not in readers:
            raise MissingDependencyError(f"Installed Pandoc has no {reader} reader; upgrade Pandoc to read {suffix}.")
        completed = subprocess.run([executable, "--sandbox", "--from", reader,
            "--to", "gfm+tex_math_dollars+raw_html", str(path.resolve())],
            capture_output=True, encoding="utf-8", timeout=options.timeout, check=True)
        issues = [("legacy_layout_unverified",
            "Legacy document structure was converted by Pandoc; visual objects and original layout require inspection.")]
        if completed.stderr.strip():
            issues.append(("legacy_reader_warning", completed.stderr.strip()[:2000]))
        return coarse_result(path, completed.stdout, "pandoc-" + suffix[1:], issues=issues)
    if suffix not in {".doc", ".ppt"}:
        raise ValueError(f"No legacy bridge for {suffix!r}")
    target = ".docx" if suffix == ".doc" else ".pptx"
    executable = _soffice()
    with tempfile.TemporaryDirectory(prefix="mdaddict-office-") as temporary:
        root = Path(temporary)
        # A fresh profile prevents reuse of a running user's Office process and
        # its settings. It is discarded together with the intermediate file.
        profile = root / "profile"
        try:
            subprocess.run([executable, "-env:UserInstallation=" + profile.as_uri(),
                "--headless", "--safe-mode", "--convert-to", target[1:], "--outdir", str(root), str(path.resolve())],
                capture_output=True, encoding="utf-8", timeout=options.timeout, check=True)
        except subprocess.CalledProcessError as exc:
            raise ValueError("Unreadable legacy Office document; LibreOffice conversion failed.") from exc
        converted = root / (path.stem + target)
        if not converted.is_file():
            raise ValueError(f"LibreOffice produced no {target} document; check that the source is readable and not encrypted.")
        from .extract import extract
        result = extract(converted, options=options)
        result.sha256 = sha256_file(path)
        result.source_name = path.name
        result.extractor = "libreoffice-" + suffix[1:] + "+" + result.extractor
        result.metadata["legacy"] = {"original_suffix": suffix, "intermediate_suffix": target,
            "intermediate_sha256": sha256_file(converted), "locator_basis": "converted office representation",
            "blocks": [asdict(block.source) for block in result.blocks]}
        result.issues.append(ExtractionIssue("legacy_layout_unverified",
            "Locators describe a LibreOffice conversion, not original DOC/PPT geometry; fidelity requires review.",
            SourceLocator(), [b.id for b in result.blocks], "unresolved"))
        result.refresh_status()
        return result
