"""Lazy feature checks; installing the core requires no third-party packages."""
from importlib.util import find_spec
from pathlib import Path


class MissingDependencyError(RuntimeError):
    """A selected format or feature needs an optional dependency."""


def require_format(path: Path) -> None:
    requirements = {
        ".pdf": ("pdf", ("pypdf", "PIL")),
        ".pptx": ("office", ("pptx", "lxml", "PIL")),
        ".docx": ("office", ("lxml", "PIL")),
        ".xlsx": ("office", ("openpyxl",)),
    }
    suffix = path.suffix.lower()
    from .capabilities import IMAGE_TYPES
    if suffix in {".heic", ".heif"}:
        extra, modules = "heif", ("PIL", "pillow_heif")
    elif suffix in IMAGE_TYPES:
        extra, modules = "images", ("PIL",)
    elif suffix in requirements:
        extra, modules = requirements[suffix]
    else:
        return
    missing = [name for name in modules if find_spec(name) is None]
    if suffix == ".pdf":
        # Either permissive pdfium or optional PyMuPDF stack satisfies PDF.
        if find_spec("pypdfium2") is None and (find_spec("pymupdf") is None or find_spec("pymupdf4llm") is None):
            missing = list(dict.fromkeys([*missing, "pypdfium2"]))
        else:
            missing = [name for name in missing if name not in {"pypdfium2", "pymupdf", "pymupdf4llm"}]
    if missing:
        raise MissingDependencyError(f"Missing {', '.join(missing)}; install with pip install 'mdaddict[{extra}]'.")
