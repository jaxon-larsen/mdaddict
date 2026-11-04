"""Bounded, provider-free input normalization and conservative reader detection."""
from __future__ import annotations

import codecs
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import io
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import BinaryIO
import time
import zipfile

from .capabilities import LOCAL_TYPES, TEXT_TYPES, capabilities
from .strategy import ExtractOptions

InputSource = str | os.PathLike[str] | bytes | bytearray | BinaryIO

DETECTION_REVISION = 1


@dataclass(frozen=True)
class Detection:
    suffix: str
    encoding: str
    warnings: tuple[str, ...] = ()

    def metadata(self):
        return {"revision": DETECTION_REVISION, **asdict(self), "warnings": list(self.warnings)}


def _encoding(data: bytes, encoding: str) -> str:
    bom = None
    for mark, name in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                       (codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"),
                       (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(mark):
            bom = name
            break
    if encoding != "auto":
        try:
            canonical = codecs.lookup(encoding).name
        except LookupError as error:
            raise ValueError(f"Unknown encoding {encoding!r}; specify a valid encoding") from error
        compatible = {"utf-8-sig": {"utf-8", "utf-8-sig"}, "utf-16": {"utf-16", "utf-16-le", "utf-16-be"},
                      "utf-32": {"utf-32", "utf-32-le", "utf-32-be"}}
        if bom == "utf-16" and canonical in {"utf-16-le", "utf-16-be"}:
            compatible[bom] = {"utf-16", "utf-16-le" if data.startswith(codecs.BOM_UTF16_LE) else "utf-16-be"}
        if bom == "utf-32" and canonical in {"utf-32-le", "utf-32-be"}:
            compatible[bom] = {"utf-32", "utf-32-le" if data.startswith(codecs.BOM_UTF32_LE) else "utf-32-be"}
        if bom and canonical not in compatible[bom]:
            raise ValueError(f"Explicit encoding {encoding!r} conflicts with {bom} BOM")
        return encoding
    return bom or "utf-8-sig"


def detect_input(data: bytes, *, name: str = "", content_type: str | None = None,
                 options: ExtractOptions | None = None) -> Detection:
    """Resolve reader without optional imports or acquisition; MIME is only a hint."""
    options = options or ExtractOptions()
    if not data:
        raise ValueError("Empty input")
    if len(data) > options.max_mb * 1024 * 1024:
        raise ValueError(f"Input exceeds --max-mb {options.max_mb}")
    hint = Path(name).suffix.lower()
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    mime_suffixes = {ext for cap in capabilities() if mime and mime in cap.mime_types for ext in cap.extensions}
    if hint not in LOCAL_TYPES:
        hint = next(iter(mime_suffixes)) if len(mime_suffixes) == 1 else ""
    strong = ""
    for magic, suffix in ((b"%PDF-", ".pdf"), (b"\x89PNG\r\n\x1a\n", ".png"),
                          (b"\xff\xd8\xff", ".jpg"), (b"GIF87a", ".gif"), (b"GIF89a", ".gif"),
                          (b"II*\x00", ".tif"), (b"MM\x00*", ".tif"),
                          (b"fLaC", ".flac"), (b"{\\rtf", ".rtf")):
        if data.startswith(magic):
            strong = suffix
            break
    # Short printable prefixes alone are not evidence: BM25 and ID3 can be prose.
    if data.startswith(b"BM") and len(data) >= 26:
        declared_size, offset = struct.unpack_from("<I", data, 2)[0], struct.unpack_from("<I", data, 10)[0]
        if declared_size == len(data) and 26 <= offset <= len(data):
            strong = ".bmp"
    if data.startswith(b"ID3") and len(data) >= 10 and data[3] in {2, 3, 4} and all(v < 128 for v in data[6:10]):
        strong = ".mp3"
    if data.startswith(b"RIFF") and len(data) >= 12:
        strong = {b"WEBP": ".webp", b"WAVE": ".wav", b"AVI ": ".avi"}.get(data[8:12], "")
    if data.startswith((b"MZ", b"\x7fELF")):
        raise ValueError("Unsupported executable content")
    if data.startswith(b"PK\x03\x04") or data.startswith(b"PK\x05\x06"):
        try:
            # Bound entry allocation before ZipFile materializes the directory.
            end = data.rfind(b"PK\x05\x06", max(0, len(data) - 65557))
            if end < 0 or end + 22 > len(data):
                raise ValueError("Invalid ZIP/Office container directory")
            entries = struct.unpack_from("<H", data, end + 10)[0]
            if entries == 65535 or entries > max(10000, options.max_archive_members):
                raise ValueError("Container member inspection limit exceeded (ZIP64 not detected)")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if len(members) > max(10000, options.max_archive_members):
                    raise ValueError("Container member inspection limit exceeded")
                if sum(item.file_size for item in members) > options.max_expanded_mb * 1024 * 1024:
                    raise ValueError("Expanded container exceeds resource limit")
                names = {item.filename for item in members}
                candidates = [suffix for marker, suffix in (("word/document.xml", ".docx"),
                    ("ppt/presentation.xml", ".pptx"), ("xl/workbook.xml", ".xlsx")) if marker in names]
                if "mimetype" in names:
                    member = archive.getinfo("mimetype")
                    if member.file_size > 256:
                        raise ValueError("Invalid container mimetype")
                    kind = archive.read(member)
                    if kind == b"application/epub+zip":
                        candidates.append(".epub")
                    elif kind == b"application/vnd.oasis.opendocument.text":
                        candidates.append(".odt")
                if len(candidates) > 1:
                    raise ValueError("Ambiguous container: multiple document families")
                strong = candidates[0] if candidates else ".zip"
        except zipfile.BadZipFile as error:
            raise ValueError("Invalid ZIP/Office container") from error
    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        if hint not in {".doc", ".ppt", ".xls", ".msg"}:
            raise ValueError("Ambiguous OLE container; supply a .doc, .ppt, .xls or .msg name")
        strong = hint
    encoding = _encoding(data, options.encoding)
    if not strong:
        try:
            text = data.decode(encoding)
        except UnicodeError as error:
            if hint and hint not in TEXT_TYPES | {".csv", ".tsv", ".tab", ".html", ".htm", ".xhtml", ".srt", ".vtt", ".ipynb", ".rss", ".atom", ".eml"}:
                # Signatureless formats still require their named reader to validate them.
                strong = hint
            else:
                raise ValueError("Cannot decode text; specify encoding explicitly (no replacement characters inserted)") from error
        else:
            if any(ord(c) < 32 and c not in "\t\r\n\f" for c in text):
                raise ValueError("Unknown binary content; no compatible reader detected")
            head = text.lstrip()[:8192]
            if re.match(r"(?is)(?:<!doctype\s+html\b|<html\b)", head):
                strong = ".html"
            elif head.startswith("WEBVTT"):
                strong = ".vtt"
            elif head.startswith("{") and len(data) <= 1024 * 1024:
                try:
                    obj = json.loads(text)
                    if isinstance(obj, dict) and isinstance(obj.get("cells"), list) and isinstance(obj.get("nbformat"), int):
                        strong = ".ipynb"
                except ValueError:
                    pass
            # Explicit text/delimited/document hints preserve their semantics.
            strong = strong or hint or ".txt"
    warnings = []
    supplied = Path(name).suffix.lower()
    # Alias extensions select the same reader and are kept stable across paths.
    aliases = ({".jpg", ".jpeg", ".jpe"}, {".tif", ".tiff"}, {".html", ".htm", ".xhtml"})
    if any(strong in group and supplied in group for group in aliases):
        strong = supplied
    if supplied and supplied != strong:
        warnings.append(f"Detected {strong} content differs from filename extension {supplied}; using {strong} reader")
    if mime and mime != "application/octet-stream" and mime_suffixes and strong not in mime_suffixes:
        warnings.append(f"Detected {strong} content conflicts with declared MIME {mime}; using {strong} reader")
    return Detection(strong, encoding, tuple(warnings))


@contextmanager
def normalized_input(source: InputSource, *, options: ExtractOptions, name: str | None = None,
                     content_type: str | None = None):
    """Read a bounded snapshot. Caller streams advance and are never closed.

    Deadlines are checked between reads. A caller's blocking read cannot be
    interrupted in-process; use the app's killable worker for hard deadlines.
    """
    path = Path(source).resolve() if isinstance(source, (str, os.PathLike)) else None
    display = Path((name or (path.name if path else "input")).replace("\\", "/")).name or "input"
    maximum = options.max_mb * 1024 * 1024
    if path and path.stat().st_size > maximum:
        raise ValueError(f"Input exceeds --max-mb {options.max_mb}")
    if isinstance(source, (bytes, bytearray)) and len(source) > maximum:
        raise ValueError(f"Input exceeds --max-mb {options.max_mb}")
    if path is None and not isinstance(source, (bytes, bytearray)) and not callable(getattr(source, "read", None)):
        raise ValueError("Input must be a path, bytes or a binary readable stream")
    stream = path.open("rb") if path else io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    deadline = time.monotonic() + options.timeout
    try:
        chunks = bytearray()
        while True:
            if time.monotonic() > deadline:
                raise ValueError("Input read timeout")
            chunk = stream.read(min(65536, maximum + 1 - len(chunks)))
            if time.monotonic() > deadline:
                raise ValueError("Input read timeout")
            if not isinstance(chunk, bytes):
                raise ValueError("Input must be bytes or a binary readable stream")
            chunks.extend(chunk)
            if len(chunks) > maximum:
                raise ValueError(f"Input exceeds --max-mb {options.max_mb}")
            if not chunk:
                break
        data = bytes(chunks)
    finally:
        if path or isinstance(source, (bytes, bytearray)):
            stream.close()
    detection = detect_input(data, name=display, content_type=content_type, options=options)
    effective = replace(options, encoding=detection.encoding)
    if path and path.suffix.lower() == detection.suffix:
        digest = hashlib.sha256(data).digest()
        def unchanged():
            from .strategy import sha256_file
            if sha256_file(path) != digest.hex():
                raise RuntimeError("Input changed during detection or conversion")
        unchanged()
        yield path, display, detection, effective
        unchanged()
    else:
        with tempfile.TemporaryDirectory(prefix="mdaddict-input-") as directory:
            temporary = Path(directory) / (Path(display).stem + detection.suffix)
            temporary.write_bytes(data)
            yield temporary, display, detection, effective
