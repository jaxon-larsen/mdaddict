"""Validation, versioned cache lookup, and strategy dispatch."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import time
import zipfile
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from mdaddict.ai import AIProvider

from mdaddict.strategy import ENGINE_REVISION, ExtractOptions, ExtractResult, filesystem_path, load_extract, normalize, sha256_file, write_extract

from mdaddict.capabilities import TEXT_TYPES, IMAGE_TYPES, LOCAL_TYPES, AUDIO_TYPES, VIDEO_TYPES
SUPPORTED = LOCAL_TYPES


@lru_cache(maxsize=1)
def dependency_versions() -> dict:
    versions = {}
    for name in ("pypdfium2", "pymupdf", "pymupdf4llm", "pypdf", "python-pptx", "pillow", "openpyxl", "boto3", "markdownify", "beautifulsoup4", "markitdown", "pandas", "xlrd", "olefile", "pysubs2", "pillow-heif", "youtube-transcript-api"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    for binary in ("pandoc", "tesseract", "ffmpeg", "soffice", "libreoffice"):
        if shutil.which(binary):
            run = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
            versions[binary] = (run.stdout or run.stderr).splitlines()[0]
        else:
            versions[binary] = "not-installed"
    return versions


def ocr_data_identity(options: ExtractOptions) -> dict[str, str]:
    """Fingerprint actual selected language data, not only the OCR binary."""
    if options.ocr == "off":
        return {}
    roots = []
    if os.environ.get("TESSDATA_PREFIX"):
        roots.append(Path(os.environ["TESSDATA_PREFIX"]))
    binary = shutil.which("tesseract")
    if binary:
        parent = Path(binary).parent
        roots.extend((parent / "tessdata", parent.parent / "share/tessdata", parent.parent / "share/tesseract-ocr/5/tessdata"))
        if not roots or not any(root.is_dir() for root in roots):
            run = subprocess.run([binary, "--list-langs"], capture_output=True, text=True, timeout=5)
            import re
            match = re.search(r'available languages in "([^"]+)"', run.stdout + run.stderr)
            if match:
                roots.append(Path(match[1]))
    languages = options.language.split("+")
    if any(not language or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-/" for c in language)
           or ".." in language or language.startswith("/") for language in languages):
        raise ValueError("Invalid OCR language name")
    return {language: next((sha256_file(root / f"{language}.traineddata") for root in roots
                            if (root / f"{language}.traineddata").is_file()), "not-installed") for language in languages}


def validate_input(path: Path, options: ExtractOptions) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() not in SUPPORTED:
        raise ValueError(f"Unsupported type {path.suffix!r}. Supported: {', '.join(sorted(SUPPORTED))}")
    if path.stat().st_size > options.max_mb * 1024 * 1024:
        raise ValueError(f"Input exceeds --max-mb {options.max_mb}")
    if path.suffix.lower() in {".docx", ".pptx", ".xlsx"}:
        with zipfile.ZipFile(path) as archive:
            if sum(i.file_size for i in archive.infolist()) > options.max_mb * 1024 * 1024 * 20:
                raise ValueError("Expanded Office document exceeds resource limit")


from mdaddict.dependencies import require_format


def implementation_identity(extra="") -> str:
    """Fingerprint the complete local adapter implementation, including glue."""
    return hashlib.sha256(b"".join(p.read_bytes() for p in sorted(Path(__file__).parent.rglob("*.py"))) + extra.encode()).hexdigest()


def run_extraction(path, strategy, *, options, engine_factory, provider_settings=None,
                   implementation_extra="", out_dir=None, force=False) -> ExtractResult:
    """Shared cache/integrity boundary, also used by application compatibility adapters."""
    started = time.perf_counter()
    path = Path(path).resolve()
    out_dir = Path(out_dir) if out_dir is not None else None
    validate_input(path, options)
    require_format(path)
    source_sha = sha256_file(path)
    identity = {"engine": ENGINE_REVISION, "strategy": strategy, "suffix": path.suffix.lower(),
                "options": asdict(options), "dependencies": dependency_versions()}
    if path.suffix.lower() in {".doc", ".ppt"}:
        from mdaddict.legacy import _soffice
        executable = _soffice()
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5, check=True)
        identity["legacy_tool"] = {"binary": str(executable), "version": (version.stdout or version.stderr).strip()}
    identity["ocr_traineddata"] = ocr_data_identity(options)
    if provider_settings:
        identity["provider_settings"] = provider_settings
    # Include the source revision of the engine so code-only Docker overlays cannot reuse stale extracts.
    identity["implementation"] = implementation_identity(implementation_extra)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    if out_dir and not force:
        dest = filesystem_path(out_dir.resolve() / ".cache" / "extract" / source_sha / f"{key}.md")
        try:
            result = load_extract(dest, source_sha=source_sha, cache_key=key, identity=identity)
            if sha256_file(path) != source_sha:
                raise RuntimeError("Input changed during cache lookup")
            result.source_name = path.name
            result.cache_hit = True
            result.elapsed_ms = round((time.perf_counter()-started)*1000, 2)
            return result
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Incomplete/corrupt cache is a miss, never trusted evidence.
    engine = engine_factory(strategy, options)
    if strategy != "offline" and out_dir and not force:
        engine.region_cache_dir = out_dir.resolve() / ".cache" / "vision"
    result = engine.extract(path)
    if sha256_file(path) != source_sha:
        raise RuntimeError("Input changed during conversion; output was not cached")
    result.sha256 = source_sha
    result.markdown = normalize(result.markdown)
    result.cache_key = key
    result.metadata.update(identity)
    from mdaddict.ingestion import describe_result
    describe_result(result, kind="file", path=path)
    result.elapsed_ms = round((time.perf_counter()-started)*1000, 2)
    if out_dir:
        write_extract(result, out_dir)
    return result


def extract(path: str | os.PathLike[str], *, options: ExtractOptions | None = None,
            ai_provider: AIProvider | None = None, out_dir: str | os.PathLike[str] | None = None,
            force: bool = False) -> ExtractResult:
    """Extract a local file; only an explicit provider enables AI assistance."""
    options = options or ExtractOptions()
    suffix = Path(path).suffix.lower()
    if suffix in AUDIO_TYPES | VIDEO_TYPES:
        from mdaddict.ai import validate_provider, provider_modalities
        from mdaddict.media import transcribe_media
        if ai_provider is None or "audio" not in provider_modalities(ai_provider):
            raise ValueError("Media transcription requires an explicitly supplied provider with the 'audio' modality")
        settings = validate_provider(ai_provider)
        class MediaExtractor:
            def extract(self, source):
                return transcribe_media(source, provider=ai_provider, options=options)
        factory = lambda _name, opts: MediaExtractor()
        strategy = "media"
    elif ai_provider is None:
        from mdaddict.extract_offline import OfflineExtractor
        factory = lambda _name, opts: OfflineExtractor(opts)
        strategy, settings = "offline", None
    else:
        from mdaddict.ai import validate_provider
        from mdaddict.ai import provider_modalities
        from mdaddict.extract_vision import VisionExtractor
        settings = validate_provider(ai_provider)
        if "vision" not in provider_modalities(ai_provider):
            raise ValueError("File AI assistance requires the 'vision' modality")
        factory = lambda _name, opts: VisionExtractor(opts, provider=ai_provider)
        strategy = "vision"
    return run_extraction(path, strategy, options=options, engine_factory=factory,
                          provider_settings=settings, out_dir=out_dir, force=force)


def to_markdown(path: str | os.PathLike[str], *, options: ExtractOptions | None = None,
                ai_provider: AIProvider | None = None, out_dir: str | os.PathLike[str] | None = None,
                force: bool = False) -> str:
    """Convert a local file to Markdown with the same options as extract()."""
    return extract(path, options=options, ai_provider=ai_provider,
                   out_dir=out_dir, force=force).markdown
