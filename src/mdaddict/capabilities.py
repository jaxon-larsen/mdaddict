"""Versioned input catalog. Inspection performs no imports, downloads or network I/O."""
from __future__ import annotations

from dataclasses import dataclass, replace
from importlib.util import find_spec
from pathlib import Path
import shutil

CATALOG_REVISION = "mdaddict-inputs-1"
TEXT_TYPES = frozenset({".md", ".markdown", ".txt", ".text", ".rst", ".log", ".py", ".r", ".json", ".yaml", ".yml", ".xml",
    ".jsonl", ".ndjson", ".js", ".ts", ".jsx", ".tsx", ".c", ".h", ".cpp", ".hpp", ".java", ".go", ".rs", ".rb", ".sh", ".sql", ".css"})
IMAGE_TYPES = frozenset({".png", ".jpg", ".jpeg", ".jpe", ".tif", ".tiff", ".bmp", ".webp", ".gif", ".ico", ".jp2", ".ppm", ".pgm", ".pbm", ".pnm", ".tga", ".pcx", ".heic", ".heif"})
AUDIO_TYPES = frozenset({".wav", ".mp3", ".m4a", ".aac", ".wma", ".flac", ".ogg", ".oga", ".opus", ".aif", ".aiff"})
VIDEO_TYPES = frozenset({".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"})
EXTENDED_TYPES = frozenset({".xls", ".epub", ".ipynb", ".msg", ".eml", ".p7s", ".rss", ".atom", ".zip",
    ".doc", ".ppt", ".odt", ".rtf", ".org", ".adoc", ".asciidoc", ".tex", ".latex", ".opml", ".fb2", ".typ", ".srt", ".vtt"})
NATIVE_TYPES = TEXT_TYPES | IMAGE_TYPES | {".pdf", ".pptx", ".docx", ".html", ".htm", ".xhtml", ".csv", ".tsv", ".tab", ".xlsx"}
LOCAL_TYPES = NATIVE_TYPES | EXTENDED_TYPES | AUDIO_TYPES | VIDEO_TYPES


@dataclass(frozen=True)
class Capability:
    id: str
    family: str
    extensions: tuple[str, ...]
    mime_types: tuple[str, ...]
    backend: str
    extra: str = ""
    modules: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    requires_network: bool = False
    modality: str = ""
    coverage: str = "content"
    locator: str = "document"
    verification: str = "acceptance_pending"
    availability: str = "ready"
    missing: tuple[str, ...] = ()
    catalog_revision: str = CATALOG_REVISION


_CATALOG = (
    Capability("text", "text", tuple(sorted(TEXT_TYPES)), ("text/plain", "text/markdown", "application/json", "application/x-ndjson", "application/xml", "text/x-python"), "stdlib", verification="existing_suite"),
    Capability("pdf", "document", (".pdf",), ("application/pdf",), "pdfium/pypdf", "pdf", ("pypdf", "PIL"), locator="page", verification="existing_suite"),
    Capability("docx", "document", (".docx",), ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",), "native/Pandoc", "office", ("lxml", "PIL"), ("pandoc",), locator="paragraph", verification="existing_suite"),
    Capability("pptx", "presentation", (".pptx",), ("application/vnd.openxmlformats-officedocument.presentationml.presentation",), "python-pptx", "office", ("pptx", "lxml", "PIL"), locator="slide", verification="existing_suite"),
    Capability("xlsx", "spreadsheet", (".xlsx",), ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",), "openpyxl", "office", ("openpyxl",), locator="sheet", verification="existing_suite"),
    Capability("delimited", "table", (".csv", ".tsv", ".tab"), ("text/csv", "text/tab-separated-values"), "stdlib", verification="existing_suite"),
    Capability("html", "web", (".html", ".htm", ".xhtml"), ("text/html", "application/xhtml+xml"), "Markdownify/Pandoc", "html", verification="existing_suite"),
    Capability("image", "image", tuple(sorted(IMAGE_TYPES - {".heic", ".heif"})), ("image/png", "image/jpeg", "image/tiff", "image/webp", "image/gif", "image/bmp", "image/x-icon", "image/jp2"), "Pillow/Tesseract", "images", ("PIL",), coverage="frame_text", locator="image", verification="existing_suite"),
    Capability("heif", "image", (".heic", ".heif"), ("image/heic", "image/heif"), "pillow-heif/Tesseract", "heif", ("PIL", "pillow_heif"), coverage="frame_text", locator="image"),
    Capability("xls", "spreadsheet", (".xls",), ("application/vnd.ms-excel",), "MarkItDown XlsConverter", "extended", ("markitdown", "pandas", "xlrd")),
    Capability("epub", "book", (".epub",), ("application/epub+zip",), "MarkItDown EpubConverter", "extended", ("markitdown",)),
    Capability("notebook", "notebook", (".ipynb",), ("application/x-ipynb+json",), "MarkItDown IpynbConverter", "extended", ("markitdown",)),
    Capability("msg", "mail", (".msg",), ("application/vnd.ms-outlook",), "MarkItDown OutlookMsgConverter", "extended", ("markitdown", "olefile")),
    Capability("mail", "mail", (".eml", ".p7s"), ("message/rfc822", "application/pkcs7-signature"), "stdlib email", locator="part"),
    Capability("feeds", "web", (".rss", ".atom"), ("application/rss+xml", "application/atom+xml"), "MarkItDown RssConverter", "extended", ("markitdown",)),
    Capability("archive", "container", (".zip",), ("application/zip",), "bounded member dispatcher", locator="member"),
    Capability("legacy-office", "document", (".doc", ".ppt"), ("application/msword", "application/vnd.ms-powerpoint"), "LibreOffice/native", "office", ("lxml", "PIL"), ("soffice",)),
    Capability("reader", "document", (".odt", ".rtf", ".org", ".adoc", ".asciidoc", ".tex", ".latex", ".opml", ".fb2", ".typ"), ("application/vnd.oasis.opendocument.text", "application/rtf", "text/rtf", "text/org", "text/x-tex"), "Pandoc", tools=("pandoc",)),
    Capability("captions", "transcript", (".srt", ".vtt"), ("application/x-subrip", "text/vtt"), "pysubs2", "captions", ("pysubs2",), locator="segment"),
    Capability("audio", "audio", tuple(sorted(AUDIO_TYPES)), ("audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/flac", "audio/ogg", "audio/aac", "audio/x-ms-wma"), "explicit media provider", modality="audio", coverage="transcript", locator="segment_if_supplied"),
    Capability("video", "video", tuple(sorted(VIDEO_TYPES)), ("video/mp4", "video/webm", "video/quicktime", "video/x-msvideo", "video/x-matroska"), "ffmpeg/explicit audio provider", tools=("ffmpeg",), modality="audio", coverage="audio_only", locator="segment_if_supplied"),
    Capability("url", "remote", (), (), "explicit bounded HTTP acquisition", requires_network=True),
    Capability("specialized-web", "remote", (), (), "MarkItDown Wikipedia/Bing snapshots", "extended", ("markitdown",), requires_network=True, coverage="selected_static_content"),
    Capability("youtube", "remote", (), (), "youtube-transcript-api", "online", ("youtube_transcript_api",), requires_network=True, coverage="captions_only", locator="segment"),
)


def capability_for(path: str | Path, mime_type: str | None = None) -> Capability | None:
    """Resolve a pinned route; MIME is a fallback, never an automatic network call."""
    suffix = Path(path).suffix.lower()
    match = next((c for c in _CATALOG if suffix in c.extensions), None)
    if match is None and mime_type:
        mime = mime_type.split(";", 1)[0].strip().lower()
        match = next((c for c in _CATALOG if mime in c.mime_types), None)
    return match


def capabilities(*, allow_network: bool = False, ai_provider=None) -> tuple[Capability, ...]:
    """Report configuration availability, separately from fidelity verification."""
    from .ai import provider_modalities
    modalities = provider_modalities(ai_provider) if ai_provider is not None else frozenset()
    rows = []
    for capability in _CATALOG:
        missing = ["module:" + m for m in capability.modules if find_spec(m) is None]
        missing.extend("tool:" + t for t in capability.tools if shutil.which(t) is None)
        if capability.id == "pdf" and find_spec("pypdfium2") is None and (find_spec("pymupdf") is None or find_spec("pymupdf4llm") is None):
            missing.append("module:pypdfium2")
        if capability.id == "html" and find_spec("markdownify") is None and shutil.which("pandoc") is None:
            missing.append("module:markdownify or tool:pandoc")
        if capability.id in {"image", "heif"} and shutil.which("tesseract") is None:
            missing.append("tool:tesseract")
        if capability.requires_network and not allow_network:
            state = "network_disabled"
        elif capability.modality and capability.modality not in modalities:
            state = "missing_provider"
            missing.append("provider:" + capability.modality)
        else:
            state = "missing_dependency" if missing else "ready"
        rows.append(replace(capability, availability=state, missing=tuple(missing)))
    return tuple(rows)
