"""Measure the installed-file closure of explicit Python requirements.

This excludes Python itself, bytecode caches, external binaries and model data.
Counts describe this environment's resolved versions, not download sizes.
"""
import argparse
from importlib import metadata
import json
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement


def inventory(root):
    pending = [Requirement(root)]
    seen, names, paths = set(), set(), set()
    packages = []
    while pending:
        req = pending.pop()
        state = (req.name.lower().replace("_", "-"), tuple(sorted(req.extras)))
        if state in seen:
            continue
        seen.add(state)
        dist = metadata.distribution(req.name)
        name = dist.metadata["Name"]
        if name not in names:
            names.add(name)
            files = {Path(dist.locate_file(f)).resolve() for f in dist.files or []}
            files = {p for p in files if p.is_file() and "__pycache__" not in p.parts}
            paths.update(files)
            packages.append({"name": name, "version": dist.version,
                             "installed_file_bytes": sum(p.stat().st_size for p in files),
                             "declared_license": dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                             "license_classifiers": [c for c in dist.metadata.get_all("Classifier", []) if c.startswith("License ::")]})
        for text in dist.requires or []:
            dep = Requirement(text)
            if dep.marker is None or any(dep.marker.evaluate({**default_environment(), "extra": extra}) for extra in ("", *req.extras)):
                pending.append(dep)
    return {"requirement": root, "package_count": len(names),
            "installed_file_bytes": sum(p.stat().st_size for p in paths),
            "packages": sorted(packages, key=lambda row: row["name"].lower())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements", nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = [inventory(root) for root in args.requirements]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for row in results:
        print(json.dumps({key: value for key, value in row.items() if key != "packages"}))
