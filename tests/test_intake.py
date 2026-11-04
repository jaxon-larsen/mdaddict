"""Source-grounded bounded intake and detection regression cases."""
import hashlib
import io
import subprocess
import sys
import zipfile

import pytest

from mdaddict import ExtractOptions, detect_input, extract


def test_equivalent_entry_points_and_cache_diagnostics(tmp_path):
    data = b"The normalization condition is |a|^2 + |b|^2 = 1.\n"
    path = tmp_path / "notes.txt"
    path.write_bytes(data)
    results = [extract(source, out_dir=tmp_path / "out") for source in (path, data, io.BytesIO(data))]
    assert {r.sha256 for r in results} == {hashlib.sha256(data).hexdigest()}
    assert len({r.cache_key for r in results}) == 1
    assert all(r.markdown == data.decode() and r.blocks == results[0].blocks for r in results)
    assert results[1].cache_hit and results[2].cache_hit
    bad_name = extract(data, name="notes.unknown", out_dir=tmp_path / "out")
    assert bad_name.warnings and bad_name.source_name == "notes.unknown"
    clean = extract(path, out_dir=tmp_path / "out")
    assert clean.cache_hit and not clean.metadata["input_detection"]["warnings"]
    assert not any("Detected" in w for w in clean.warnings)


def test_stream_cursor_and_ownership():
    stream = io.BytesIO(b"prefixsource text")
    stream.seek(6)
    assert extract(stream).markdown == "source text\n"
    assert stream.tell() == len(stream.getvalue()) and not stream.closed
    class NonSeekable:
        def __init__(self): self.stream = io.BytesIO(b"source text")
        def read(self, size): return self.stream.read(size)
    assert extract(NonSeekable()).markdown == "source text\n"
    text = io.StringIO("text")
    with pytest.raises(ValueError, match="binary"):
        extract(text)
    assert not text.closed


def test_container_detection_and_ambiguity():
    def archive(names):
        target = io.BytesIO()
        with zipfile.ZipFile(target, "w") as out:
            for name in names: out.writestr(name, "<source/>")
        return target.getvalue()
    assert detect_input(archive(["ppt/presentation.xml"]), name="lecture").suffix == ".pptx"
    assert detect_input(archive(["word/document.xml"]), name="notes.zip").warnings
    assert detect_input(archive(["plain.txt"])).suffix == ".zip"
    with pytest.raises(ValueError, match="Ambiguous"):
        detect_input(archive(["word/document.xml", "ppt/presentation.xml"]))
    assert detect_input(b"%PDF-1.7\n", name="notes.txt").suffix == ".pdf"
    assert detect_input(b"%PDF-1.7\n", content_type="text/plain").warnings


def test_unicode_and_explicit_encoding():
    for encoding in ("utf-8-sig", "utf-16", "utf-32"):
        data = "Probability β = ½\n".encode(encoding)
        result = extract(data)
        assert result.markdown == "Probability β = ½\n"
        assert result.sha256 == hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError, match="encoding"):
        extract(b"caf\xe9")
    assert extract(b"caf\xe9", options=ExtractOptions(encoding="cp1252")).markdown == "café\n"
    with pytest.raises(ValueError, match="encoding"):
        extract(b"text", options=ExtractOptions(encoding="not-an-encoding"))


def test_rejections_and_bounded_read():
    for data in (b"", b"\x00binary", b"MZ executable"):
        with pytest.raises(ValueError): extract(data)
    stream = io.BytesIO(b"a" * (1024 * 1024 + 100))
    with pytest.raises(ValueError, match="max-mb"):
        extract(stream, options=ExtractOptions(max_mb=1))
    assert stream.tell() == 1024 * 1024 + 1 and not stream.closed
    class Broken:
        def read(self, size): raise OSError("read failed")
    with pytest.raises(OSError, match="read failed"): extract(Broken())


def test_temporary_input_cleanup_on_reader_failure(monkeypatch):
    import importlib
    module = importlib.import_module("mdaddict.extract")
    observed = []
    def fail(path, **kwargs):
        observed.append(path)
        assert path.exists()
        raise RuntimeError("reader failed")
    monkeypatch.setattr(module, "_extract_resolved", fail)
    with pytest.raises(RuntimeError): extract(b"text")
    assert observed and not observed[0].parent.exists()


def test_cli_stdin():
    run = subprocess.run([sys.executable, "-m", "mdaddict", "-", "--name", "notes.md"],
        input=b"# Original\n", capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout == b"# Original\n"


def test_explicit_encoding_conflict_and_invalid_stream():
    with pytest.raises(ValueError, match="BOM"):
        extract("β".encode("utf-16"), options=ExtractOptions(encoding="cp1252"))
    with pytest.raises(ValueError, match="BOM"):
        extract("β".encode("utf-16"), options=ExtractOptions(encoding="utf-16-be"))
    with pytest.raises(ValueError, match="binary readable stream"):
        extract(None)


def test_interrupted_input_does_not_close_caller_stream():
    class Interrupted:
        closed = False
        def read(self, size): raise KeyboardInterrupt()
        def close(self): self.closed = True
    stream = Interrupted()
    with pytest.raises(KeyboardInterrupt): extract(stream)
    assert not stream.closed


def test_zip_directory_limit_is_checked_before_entry_allocation():
    import struct
    header = bytearray(b"PK\x05\x06" + b"\x00" * 18)
    struct.pack_into('<H', header, 10, 65535)
    with pytest.raises(ValueError, match='inspection limit'):
        detect_input(bytes(header))


@pytest.mark.parametrize('data', [b'BM25 ranks source sections.', b'ID3 is a decision tree algorithm.'])
def test_printable_signature_prefix_is_not_strong_evidence(data):
    assert extract(data, name='notes.txt').markdown == data.decode() + '\n'
