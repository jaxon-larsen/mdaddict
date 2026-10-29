"""Build and verify one frozen source/test snapshot; emit artifact-bound receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

PROFILES = ("core", "pdf", "pdf-pymupdf", "office", "images", "html", "extended", "captions", "heif", "online", "all")
INPUTS = ("pyproject.toml", "README.md", "src", "tests", "tools/verify_distribution.py")


def input_files(root: Path):
    for name in (*INPUTS, "LICENSE"):
        item = root / name
        if not item.exists():
            continue
        candidates = item.rglob("*") if item.is_dir() else (item,)
        for path in sorted(candidates):
            if path.is_file() and not any(part in {"__pycache__", ".pytest_cache"} for part in path.parts) and path.suffix != ".pyc":
                yield path


def inventory(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in input_files(root)}


def freeze(source: Path, snapshot: Path) -> str:
    before = inventory(source)
    for name in before:
        destination = snapshot / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, destination)
    if before != inventory(source) or before != inventory(snapshot):
        raise RuntimeError("Verification inputs changed while snapshotting; retry from a stable checkout")
    return hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", nargs="+", choices=PROFILES, default=["core"])
    parser.add_argument("--out", type=Path, default=Path("out/verification"))
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1]
    output = args.out.resolve()
    if output.exists():
        raise ValueError("Verification output already exists; select a fresh --out directory")
    output.mkdir(parents=True)
    manifest = {"status": "running", "python": sys.version.split()[0], "platform": sys.platform, "profiles": {}}
    receipt = output / "manifest.json"

    def save():
        receipt.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def run(stage, command, cwd):
        print("Verifying " + stage, flush=True)
        log = output / (stage + ".log")
        with log.open("wb") as stream:
            completed = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
        if completed.returncode:
            manifest.update(status="failed", failed_stage=stage)
            save()
            print(log.read_text(encoding="utf-8", errors="replace")[-16000:], file=sys.stderr)
            raise subprocess.CalledProcessError(completed.returncode, command)
        return log

    with TemporaryDirectory(prefix="mdaddict-verification-") as directory:
        snapshot = Path(directory)
        manifest["inputs_sha256"] = freeze(source, snapshot)
        save()
        dist = output / "dist"
        run("build", [sys.executable, "-m", "build", str(snapshot), "--outdir", str(dist)], snapshot)
        artifacts = sorted(dist.iterdir())
        manifest["artifacts"] = {path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in artifacts}
        save()
        run("metadata", [sys.executable, "-m", "twine", "check", "--strict", *map(str, artifacts)], snapshot)
        for profile in dict.fromkeys(args.profiles):
            log = run(profile, [sys.executable, str(snapshot / "tests/check_distribution.py"),
                "--dist", str(dist), "--extra", profile], snapshot)
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            summary = next(json.loads(line) for line in reversed(lines) if line.startswith('{"distribution_check":'))
            manifest["profiles"][profile] = summary
            save()
        if manifest["inputs_sha256"] != hashlib.sha256(json.dumps(inventory(snapshot), sort_keys=True).encode()).hexdigest():
            raise RuntimeError("Frozen verification inputs were mutated")
        if manifest["artifacts"] != {path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in artifacts}:
            raise RuntimeError("Verified distribution artifacts were mutated")
        manifest["status"] = "passed"
        save()
    print(json.dumps({"verification": "passed", "manifest": str(receipt), "profiles": list(manifest["profiles"])}))


if __name__ == "__main__":
    main()
