"""Shared extraction contract. Cleanup must not change source meaning."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

ENGINE_REVISION = "mdaddict-7"


@dataclass(frozen=True)
class ExtractOptions:
    encoding: str = "utf-8-sig"
    ocr: str = "auto"
    language: str = "eng"
    ai_mode: str = "auto"
    model_id: str = ""
    region: str = "us-east-1"
    max_mb: int = 25
    max_pages: int | None = None
    max_cells: int = 100_000
    max_ai_pages: int = 20
    max_ai_requests: int | None = None
    workers: int = 3
    dpi: int = 150
    timeout: int = 90
    max_tokens: int = 8192
    # Transition: auto prefers PyMuPDF if installed; otherwise PDFium.
    pdf_backend: str = "auto"
    max_archive_members: int = 200
    max_archive_depth: int = 3
    max_expanded_mb: int = 500

    def __post_init__(self):
        if self.ocr not in {"auto", "off", "force"}:
            raise ValueError("ocr must be auto, off, or force")
        if self.pdf_backend not in {"auto", "pdfium", "pymupdf"}:
            raise ValueError("pdf_backend must be auto, pdfium, or pymupdf")
        if self.ai_mode not in {"auto", "all"}:
            raise ValueError("ai_mode must be auto or all")
        if self.max_ai_requests is not None and (isinstance(self.max_ai_requests, bool) or not isinstance(self.max_ai_requests, int) or self.max_ai_requests < 0):
            raise ValueError("max_ai_requests must be nonnegative")
        if self.max_pages is not None and (not isinstance(self.max_pages, int) or isinstance(self.max_pages, bool) or self.max_pages <= 0):
            raise ValueError("max_pages must be a positive integer when supplied")
        for name in ("max_mb", "max_cells", "max_ai_pages", "workers", "dpi", "timeout", "max_tokens", "max_archive_members", "max_archive_depth", "max_expanded_mb"):
            if not isinstance(getattr(self, name), int) or isinstance(getattr(self, name), bool) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.workers > 8 or self.dpi > 300:
            raise ValueError("workers must be <=8 and dpi <=300")


@dataclass
class SourceLocator:
    unit: str = "document"
    index: int = 1
    element: str = ""


@dataclass
class SourceBlock:
    id: str
    kind: str
    source: SourceLocator
    start: int
    end: int
    method: str = "native"

    def __post_init__(self):
        if isinstance(self.source, dict):
            self.source = SourceLocator(**self.source)


from .review import VISUAL_ISSUE_CODES, effective_severity


@dataclass
class ExtractionIssue:
    code: str
    message: str
    source: SourceLocator = field(default_factory=SourceLocator)
    block_ids: list[str] = field(default_factory=list)
    severity: str = "review"

    def __post_init__(self):
        if isinstance(self.source, dict):
            self.source = SourceLocator(**self.source)
        self.severity = effective_severity(self)


@dataclass
class ExtractResult:
    sha256: str
    markdown: str
    source_name: str
    extractor: str
    pages: int = 1
    warnings: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    elapsed_ms: float = 0
    cache_hit: bool = False
    cache_key: str = ""
    schema_version: str = "1.0"
    blocks: list[SourceBlock] = field(default_factory=list)
    issues: list[ExtractionIssue] = field(default_factory=list)
    status: str = "success"
    review_status: str = "not_reviewed"

    def __post_init__(self):
        self.blocks = [SourceBlock(**b) if isinstance(b, dict) else b for b in self.blocks]
        self.issues = [ExtractionIssue(**i) if isinstance(i, dict) else i for i in self.issues]
        self.validate_contract()

    def validate_contract(self):
        if self.schema_version != "1.0":
            raise ValueError("Unsupported extraction result schema")
        integer = lambda value: isinstance(value,int) and not isinstance(value,bool)
        if not isinstance(self.markdown,str) or not integer(self.pages) or self.pages < 0:
            raise ValueError("Invalid Markdown/page count types")
        ids = {b.id for b in self.blocks}
        if len(ids) != len(self.blocks):
            raise ValueError("Duplicate source block IDs")
        for block in self.blocks:
            if block.method not in {"native", "ocr", "ai", "mixed"}:
                raise ValueError("Invalid extraction method")
            if not integer(block.start) or not integer(block.end) or not 0 <= block.start <= block.end <= len(self.markdown):
                raise ValueError("Source block span outside Markdown")
            if not integer(block.source.index) or block.source.index < 1:
                raise ValueError("Source indices are one-based")
        for issue in self.issues:
            if issue.severity not in {"review", "unresolved", "informational"} or not integer(issue.source.index) or issue.source.index < 1:
                raise ValueError("Invalid issue severity/source")
            if not set(issue.block_ids) <= ids:
                raise ValueError("Issue references unknown source blocks")
        if self.status not in {"success", "partial", "failure"} or self.review_status not in {"not_reviewed", "needs_review", "reviewed"}:
            raise ValueError("Invalid extraction/review state")

    def refresh_status(self):
        self.status = "partial" if any(i.severity == "unresolved" for i in self.issues) else "success"
        self.review_status = "needs_review" if any(i.severity != "informational" for i in self.issues) else "not_reviewed"
        self.validate_contract()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(text: str) -> str:
    """Only normalize transport newlines/BOM; preserve math, cells and code."""
    text = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    return text if not text or text.endswith("\n") else text + "\n"


def comment(value: str) -> str:
    return value.replace("--", "—").replace("\n", " ").replace("\r", " ")


def figure(description: str = "unresolved image") -> str:
    return f"<!-- fig: {comment(description)} -->"


def table_markdown(rows: list[list[str]], max_cells: int = 100_000) -> str:
    if not rows:
        return ""
    width = max(map(len, rows))
    if width * len(rows) > max_cells:
        raise ValueError(f"Rectangular table exceeds {max_cells} cells after padding")
    if not width:
        return ""
    def cell(value):
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>")
    lines = ["| " + " | ".join(cell(c) for c in row + [""] * (width-len(row))) + " |" for row in rows]
    lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
    return "\n".join(lines)


def filesystem_path(path: Path | str) -> Path:
    """Use Windows extended paths for deep notebook/cache locations."""
    if os.name != "nt":
        return Path(path)
    absolute = os.path.abspath(path)
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    return Path("\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute)


def atomic_write(path: Path, content: str) -> None:
    path = filesystem_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".mdaddict-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_extract(path: Path, *, source_sha: str | None = None, cache_key: str | None = None,
                 identity: dict | None = None) -> ExtractResult:
    """One trust boundary for cache replay and post-write verification."""
    path = filesystem_path(path)
    payload = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Extraction metadata must be an object")
    body = path.read_text(encoding="utf-8")
    if payload.pop("markdown_sha256", None) != hashlib.sha256(body.encode()).hexdigest():
        raise ValueError("Persisted Markdown hash mismatch")
    if source_sha is not None and payload.get("sha256") != source_sha:
        raise ValueError("Persisted source identity mismatch")
    if cache_key is not None and payload.get("cache_key") != cache_key:
        raise ValueError("Persisted cache identity mismatch")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or (identity is not None and any(metadata.get(k) != v for k, v in identity.items())):
        raise ValueError("Persisted implementation/options identity mismatch")
    try:
        result = ExtractResult(markdown=body, **payload)
        result.validate_contract()
    except (TypeError, AttributeError, KeyError) as error:
        raise ValueError("Malformed persisted extraction contract") from error
    return result


def write_extract(result: ExtractResult, out_dir: Path) -> Path:
    result.validate_contract()
    cache = out_dir.resolve() / ".cache" / "extract" / result.sha256
    key = result.cache_key or hashlib.sha256(result.extractor.encode()).hexdigest()[:24]
    dest = cache / f"{key}.md"
    body = normalize(result.markdown)
    payload = asdict(result)
    payload.pop("markdown")
    payload["markdown_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    atomic_write(dest, body)
    atomic_write(dest.with_suffix(".json"), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    reopened = load_extract(dest, source_sha=result.sha256, cache_key=result.cache_key, identity=result.metadata)
    if asdict(reopened) != {**asdict(result), "markdown": body}:
        raise ValueError("Persisted extraction differs after reopening")
    return dest


def count_formula_failures(markdown: str) -> int:
    return markdown.count("formula-not-decoded")
