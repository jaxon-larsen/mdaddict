"""Standard-library smoke check run by a clean interpreter outside the checkout."""
from importlib import metadata, resources
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory


def main():
    from mdaddict import MissingDependencyError, extract, to_markdown

    os.environ["EXTRACT_STRATEGY"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "not-a-real-key"

    def no_network(*args, **kwargs):
        raise AssertionError("Conversion attempted a network connection")

    socket.create_connection = no_network
    socket.socket.connect = no_network
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "notes.md"
        text = "# Source\n\nKeep λ, ﬁ, $x^2$, and literal $3.\n"
        source.write_text(text, encoding="utf-8")
        result = extract(str(source))
        assert to_markdown(source) == result.markdown == text
        assert result.metadata["strategy"] == "offline"
        assert result.usage.get("requests", 0) == 0
        result.validate_contract()
        assert list(root.iterdir()) == [source]
        csv = root / "table.csv"
        csv.write_text("A,B\n1,2\n", encoding="utf-8")
        assert "| 1 | 2 |" in to_markdown(csv)
        assert not any(name.split(".")[0] in {
            "engine", "pymupdf", "pymupdf4llm", "pypdf", "PIL", "pptx", "openpyxl", "lxml", "boto3", "markdownify", "bs4",
        } for name in sys.modules)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        command = [sys.executable, "-m", "mdaddict", str(source), "--json"]
        run = subprocess.run(command, cwd=root, env=env, text=True, encoding="utf-8", capture_output=True, check=True)
        assert json.loads(run.stdout)["markdown"] == text
        command = Path(sys.executable).parent / ("mdaddict.exe" if os.name == "nt" else "mdaddict")
        run = subprocess.run([str(command), str(source)], cwd=root, env=env,
                             text=True, encoding="utf-8", capture_output=True, check=True)
        assert run.stdout == text
        # Core-only installations report missing features without importing them.
        if not any(metadata.distributions(name="pymupdf")):
            pdf = root / "missing.pdf"
            pdf.write_bytes(b"dependency check occurs before parsing")
            try:
                extract(pdf)
            except MissingDependencyError as error:
                assert "mdaddict[pdf]" in str(error)
            else:
                raise AssertionError("Core silently accepted a missing PDF dependency")
    schema = json.loads(resources.files("mdaddict").joinpath("schema/extract-result.schema.json").read_text())
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    required = metadata.requires("mdaddict") or []
    assert all("extra ==" in requirement for requirement in required), required
    print(json.dumps({"installed_smoke": "passed", "version": metadata.version("mdaddict"),
                      "python": sys.version.split()[0], "platform": sys.platform}))


if __name__ == "__main__":
    main()
