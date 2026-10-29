"""Standalone conversion and explicit acquisition command."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .ingestion import ingest
from .capabilities import capabilities
from .strategy import ExtractOptions, atomic_write


def main(argv: list[str] | None = None) -> int:
    # Redirected Windows streams otherwise use the legacy console code page.
    # Markdown/JSON pipes have a fixed UTF-8 contract, including without PYTHONUTF8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="mdaddict", description="Convert files to Markdown; remote sources require explicit opt-in")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--capabilities", action="store_true", help="Print the input catalog and installed feature availability as JSON")
    parser.add_argument("--kind", choices=["file", "url", "youtube"], default="file")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--out", type=Path, help="Optional persistent output/cache directory")
    parser.add_argument("--output", type=Path, help="Optional Markdown export filename")
    parser.add_argument("--json", action="store_true", help="Print the complete structured result")
    parser.add_argument("--force", action="store_true", help="Ignore cached conversion")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--ocr", choices=["auto", "off", "force"], default="auto")
    parser.add_argument("--pdf-backend", choices=["auto", "pdfium", "pymupdf"], default="auto",
                        dest="pdf_backend")
    parser.add_argument("--language", default="eng")
    parser.add_argument("--max-pages", type=int)
    for name, default in {"max-mb": 25, "max-cells": 100_000, "workers": 3,
                          "dpi": 150, "timeout": 90, "max-archive-members": 200,
                          "max-archive-depth": 3, "max-expanded-mb": 500}.items():
        parser.add_argument("--" + name, type=int, default=default)
    args = parser.parse_args(argv)
    if args.capabilities:
        print(json.dumps([asdict(row) for row in capabilities(allow_network=args.allow_network)]))
        return 0
    if args.path is None:
        parser.error("path is required unless --capabilities is used")
    try:
        if args.kind == "file" and args.output is not None and args.output.resolve() == Path(args.path).resolve():
            raise ValueError("--output must not overwrite the input")
        options = ExtractOptions(**{name: getattr(args, name) for name in (
            "encoding", "ocr", "pdf_backend", "language", "max_pages", "max_mb", "max_cells",
            "workers", "dpi", "timeout", "max_archive_members", "max_archive_depth", "max_expanded_mb")})
        with redirect_stdout(sys.stderr):
            result = ingest(args.path, kind=args.kind, allow_network=args.allow_network,
                            options=options, out_dir=args.out, force=args.force)
        if args.output is not None:
            atomic_write(args.output, result.markdown)
        if args.json:
            print(json.dumps(asdict(result), ensure_ascii=False))
        else:
            sys.stdout.write(result.markdown)
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return 0
    except Exception as error:
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
