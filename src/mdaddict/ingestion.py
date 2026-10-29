"""Public ingestion boundary; remote access always requires explicit opt-in."""
from __future__ import annotations

import os
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .capabilities import CATALOG_REVISION, capability_for
from .strategy import ExtractOptions, ExtractResult, write_extract


def describe_result(result: ExtractResult, *, kind: str, path=None):
    capability = capability_for(path) if path is not None else None
    previous = result.metadata.get("ingestion", {}) if kind == "url" else {}
    result.metadata["ingestion"] = {
        "revision": 1, "catalog_revision": CATALOG_REVISION, "kind": kind,
        "capability": capability.id if capability else previous.get("capability", kind),
        "coverage": capability.coverage if capability else previous.get("coverage", "captions_only" if kind == "youtube" else "downloaded_artifact"),
        "locator_units": sorted({block.source.unit for block in result.blocks}),
        "verification": "source_review_required" if result.review_status == "needs_review" else "not_independently_verified",
        "original_sha256": result.sha256,
    }
    result.validate_contract()
    return result


def ingest(source: str | os.PathLike[str], *, kind: str = "file", allow_network: bool = False,
           options: ExtractOptions | None = None, ai_provider=None, out_dir=None,
           force: bool = False) -> ExtractResult:
    """Convert a file, snapshot a public URL, or acquire existing YouTube captions.

    Remote snapshots are fetched afresh; conversion caches are content-bound.
    Original downloads/caption responses are retained in metadata (base64), or
    under out_dir/.sources when an output directory is supplied.
    """
    if kind == "file":
        from .extract import extract
        return extract(source, options=options, ai_provider=ai_provider, out_dir=out_dir, force=force)
    if kind not in {"url", "youtube"}:
        raise ValueError("kind must be 'file', 'url', or 'youtube'")
    from .acquisition import acquire
    from .extract import dependency_versions, implementation_identity
    options = options or ExtractOptions()
    result = acquire(str(source), kind=kind, allow_network=allow_network,
                     options=options, ai_provider=ai_provider,
                     out_dir=out_dir, force=force)
    describe_result(result, kind=kind)
    result.metadata.setdefault("dependencies", dependency_versions())
    result.metadata["acquisition_identity"] = {"options": asdict(options),
        "dependencies": dependency_versions(), "implementation": implementation_identity(),
        "catalog_revision": CATALOG_REVISION}
    # Origin-specific evidence must never overwrite the local-file cache entry
    # or leak a prior URL into a later conversion of identical uploaded bytes.
    result.cache_key = hashlib.sha256(json.dumps({"conversion": result.cache_key, "kind": kind,
        "source": str(source), "sha256": result.sha256,
        "identity": result.metadata["acquisition_identity"]}, sort_keys=True).encode()).hexdigest()[:24]
    if out_dir is not None:
        write_extract(result, Path(out_dir))
    return result
