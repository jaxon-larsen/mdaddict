"""Inspect built artifacts and exercise an isolated installed wheel."""
import argparse
from email.parser import Parser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import venv
import zipfile


def inspect(wheel: Path, sdist: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "mdaddict/schema/extract-result.schema.json" in names
        assert "mdaddict/py.typed" in names
        for name in ("omml2latex.py", "NOTICE", "README.md", "licenses/omml2latex-LICENSE"):
            assert f"mdaddict/_vendor/{name}" in names
        assert all(name.startswith(("mdaddict/", "mdaddict-0.1.0.dist-info/")) for name in names)
        assert not any("/tests/" in name or "__pycache__" in name for name in names)
        metadata = Parser().parsestr(archive.read("mdaddict-0.1.0.dist-info/METADATA").decode())
        assert metadata["Requires-Python"] == ">=3.12"
        assert all("extra ==" in requirement for requirement in metadata.get_all("Requires-Dist", []))
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        assert any(name.endswith("tests/installed_smoke.py") for name in names)
        assert any(name.endswith("src/mdaddict/_vendor/licenses/omml2latex-LICENSE") for name in names)
        assert not any(part in name for name in names for part in (
            "/.venv/", "/out/", "/.cache/", "/engine/", "/api/", "nielsen", "wasserman",
        ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extra", choices=["core", "pdf", "pdf-pymupdf", "office", "images", "html", "extended", "captions", "heif", "online", "all"], required=True)
    parser.add_argument("--dist", type=Path, default=Path(__file__).parents[1] / "dist")
    args = parser.parse_args()
    wheel = (args.dist / "mdaddict-0.1.0-py3-none-any.whl").resolve()
    inspect(wheel, (args.dist / "mdaddict-0.1.0.tar.gz").resolve())
    tests = Path(__file__).resolve().parent
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONUTF8", "PYTHONIOENCODING"):
        env.pop(key, None)
    if args.extra == "all":
        # Cross-platform CI must exercise external integrations, not skip them.
        for binary in ("pandoc", "tesseract"):
            if shutil.which(binary) is None:
                raise RuntimeError(f"Full CI verification requires {binary} on PATH")
    with TemporaryDirectory(prefix="mdaddict-installed-") as directory:
        root = Path(directory)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        python = root / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        def run(*command):
            subprocess.run([str(python), *command], cwd=root, env=env, check=True)

        requirement = str(wheel) + ("" if args.extra == "core" else f"[{args.extra}]")
        run("-m", "pip", "install", requirement)
        if args.extra in {"pdf", "all"}:
            run("-c", "from importlib.util import find_spec; "
                "assert find_spec('pypdfium2') is not None; "
                "assert find_spec('pymupdf') is None and find_spec('pymupdf4llm') is None")
            if args.extra == "all":
                run("-c", "from importlib.util import find_spec; assert find_spec('pillow_heif') is None")
        elif args.extra == "pdf-pymupdf":
            run("-c", "from importlib.util import find_spec; "
                "assert find_spec('pymupdf') is not None and find_spec('pymupdf4llm') is not None")
        if args.extra == "core":
            run(str(tests / "installed_smoke.py"))
        run("-m", "pip", "install", "pytest>=9.1.1")
        run("-m", "pip", "check")
        run("-m", "pytest", str(tests), "--rootdir", str(tests), "--confcutdir", str(tests),
            "--import-mode=importlib", "-q")
    print(json.dumps({"distribution_check": "passed", "extra": args.extra,
                      "wheel_bytes": wheel.stat().st_size, "platform": sys.platform}))


if __name__ == "__main__":
    main()
