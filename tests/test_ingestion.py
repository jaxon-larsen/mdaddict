"""Ingestion contract and maintained adapters, using only authored local data."""
import base64
from email.message import EmailMessage
from io import BytesIO
import json
import socket
import zipfile

import pytest

from mdaddict import (AIResponse, ExtractOptions, MediaAttachment, TranscriptSegment,
                      capabilities, extract, ingest, load_extract)


def zip_bytes(members):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)
    return stream.getvalue()


def ole_bytes(streams: dict[str, bytes]) -> bytes:
    import struct
    dir_entries = []
    root_name = "Root Entry\x00".encode("utf-16le")
    dir_entries.append((root_name, len(root_name), 5, 0xffffffff, 0xffffffff, 1 if streams else 0xffffffff, 0, 0))
    sids = list(streams.keys())
    for i, (name, data) in enumerate(streams.items()):
        name_utf16 = (name + "\x00").encode("utf-16le")
        left = 0xffffffff
        right = (i + 2) if (i + 1 < len(sids)) else 0xffffffff
        child = 0xffffffff
        dir_entries.append((name_utf16, len(name_utf16), 2, left, right, child, 0, len(data)))

    num_dir_sectors = (len(dir_entries) * 128 + 511) // 512
    curr_sector = 1 + num_dir_sectors
    stream_sectors = {}
    stream_bytes = []
    for i, (name, data) in enumerate(streams.items()):
        start_sec = curr_sector
        padded_len = max(4096, ((len(data) + 511) // 512) * 512)
        padded = data + b"\x00" * (padded_len - len(data))
        stream_bytes.append(padded)
        count = len(padded) // 512
        stream_sectors[name] = (start_sec, count)
        curr_sector += count

    packed_dirs = []
    for i, entry in enumerate(dir_entries):
        name_bytes, name_len, obj_type, left, right, child, _, size = entry
        if i > 0:
            name = sids[i - 1]
            start_sec = stream_sectors[name][0]
            size = max(4096, size)
        else:
            start_sec = 0xfffffffe
            size = 0
        buf = bytearray(128)
        buf[0:len(name_bytes)] = name_bytes
        struct.pack_into("<H", buf, 0x40, name_len)
        buf[0x42] = obj_type
        buf[0x43] = 1
        struct.pack_into("<III", buf, 0x44, left, right, child)
        struct.pack_into("<I", buf, 0x74, start_sec)
        struct.pack_into("<Q", buf, 0x78, size)
        packed_dirs.append(bytes(buf))
    dir_sector_bytes = b"".join(packed_dirs)
    dir_sector_bytes += b"\x00" * (num_dir_sectors * 512 - len(dir_sector_bytes))

    fat = [0xffffffff] * 128
    fat[0] = 0xfffffffd
    for d in range(num_dir_sectors):
        fat[1 + d] = (1 + d + 1) if (d + 1 < num_dir_sectors) else 0xfffffffe
    for name, (start, count) in stream_sectors.items():
        for s in range(count):
            fat[start + s] = (start + s + 1) if (s + 1 < count) else 0xfffffffe
    fat_bytes = struct.pack("<128I", *fat)

    header = bytearray(512)
    header[0:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<H", header, 0x18, 0x003e)
    struct.pack_into("<H", header, 0x1a, 0x0003)
    struct.pack_into("<H", header, 0x1c, 0xfffe)
    struct.pack_into("<H", header, 0x1e, 9)
    struct.pack_into("<H", header, 0x20, 6)
    struct.pack_into("<I", header, 0x2c, 1)
    struct.pack_into("<I", header, 0x30, 1)
    struct.pack_into("<I", header, 0x38, 4096)
    struct.pack_into("<I", header, 0x3c, 0xfffffffe)
    struct.pack_into("<I", header, 0x44, 0xfffffffe)
    struct.pack_into("<I", header, 0x4c, 0)
    for d in range(1, 109):
        struct.pack_into("<I", header, 0x4c + d * 4, 0xffffffff)

    return bytes(header) + fat_bytes + dir_sector_bytes + b"".join(stream_bytes)


def xls_bytes(sheet_name: str, rows: list[list[float | int]]) -> bytes:
    import struct
    def biff_record(rec_type: int, data: bytes) -> bytes:
        return struct.pack("<HH", rec_type, len(data)) + data

    bof_wb = biff_record(0x0809, struct.pack("<HHHHII", 0x0600, 0x0005, 0x0dbb, 0x0cc0, 0, 0))
    name_data = struct.pack("<BB", len(sheet_name), 0) + sheet_name.encode("latin1")
    eof = biff_record(0x000A, b"")
    bof_ws = biff_record(0x0809, struct.pack("<HHHHII", 0x0600, 0x0010, 0x0dbb, 0x0cc0, 0, 0))

    nrows = len(rows)
    ncols = max((len(r) for r in rows), default=0)
    dims = biff_record(0x0200, struct.pack("<IIHHH", 0, nrows, 0, ncols, 0))

    cell_records = []
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell_records.append(biff_record(0x0203, struct.pack("<HHHd", r_idx, c_idx, 0, float(val))))

    globals_len_without_bs = len(bof_wb) + len(eof)
    bs_len = len(biff_record(0x0085, struct.pack("<IH", 0, 0) + name_data))
    sheet_offset = globals_len_without_bs + bs_len
    boundsheet = biff_record(0x0085, struct.pack("<IH", sheet_offset, 0) + name_data)

    wb_stream = bof_wb + boundsheet + eof + bof_ws + dims + b"".join(cell_records) + eof
    return ole_bytes({"Workbook": wb_stream})


def test_catalog_is_unique_and_does_not_import_readers_or_call_network(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("network"))
    rows = capabilities()
    suffixes = [suffix for row in rows for suffix in row.extensions]
    assert len(suffixes) == len(set(suffixes))
    assert next(row for row in rows if row.id == "youtube").availability == "network_disabled"
    assert next(row for row in rows if row.id == "audio").availability == "missing_provider"
    assert all(row.verification != "certified" for row in rows)


def test_remote_opt_in_precedes_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("DNS before opt-in"))
    with pytest.raises(ValueError, match="allow_network"):
        ingest("https://example.com", kind="url")
    with pytest.raises(ValueError, match="kind"):
        ingest("https://example.com", kind="auto")


def test_archive_rebases_spans_and_records_failed_members(tmp_path):
    path = tmp_path / "authored.zip"
    path.write_bytes(zip_bytes({"../../outside.txt": "α\n", "nested/data.tab": "A\tB\n1\t2\n", "unknown.bin": b"???"}))
    result = extract(path, out_dir=tmp_path / "out")
    assert result.status == "partial"
    assert not (tmp_path.parent / "outside.txt").exists()
    manifest = result.metadata["container"]["members"]
    assert [m["path"] for m in manifest] == ["../../outside.txt", "nested/data.tab", "unknown.bin"]
    assert all(len(m["sha256"]) == 64 for m in manifest)
    assert manifest[-1]["status"] == "failure"
    assert any("| 1 | 2 |" in result.markdown[b.start:b.end] for b in result.blocks)
    assert all(b.source.unit == "member" for b in result.blocks)
    assert extract(path, out_dir=tmp_path / "out").cache_hit
    result.validate_contract()


def test_recursive_archive_uses_global_budget_and_depth(tmp_path):
    path = tmp_path / "nested.zip"
    path.write_bytes(zip_bytes({"child.zip": zip_bytes({"text.txt": "source"})}))
    for options in (ExtractOptions(max_archive_depth=1), ExtractOptions(max_archive_members=1)):
        result = extract(path, options=options)
        assert result.status == "partial"
        assert any(i.code == "container_member_failed" for i in result.issues)
    many = tmp_path / "many.zip"
    many.write_bytes(zip_bytes({"a.txt": "a", "b.txt": "b"}))
    with pytest.raises(ValueError, match="max_archive_members"):
        extract(many, options=ExtractOptions(max_archive_members=1))


@pytest.mark.parametrize("container_kind", ["zip", "nested_zip", "mail"])
def test_container_preserves_office_asset_occurrences_and_spans(tmp_path, container_kind):
    import re
    from dataclasses import asdict
    from mdaddict.strategy import AssetRecord
    pptx = pytest.importorskip("pptx")
    image = pytest.importorskip("PIL.Image")
    picture = BytesIO()
    image.new("RGB", (8, 8), "blue").save(picture, format="PNG")
    deck = pptx.Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    slide.shapes.add_textbox(0, 0, 1000000, 400000).text = "α: diagram context"
    slide.shapes.add_picture(BytesIO(picture.getvalue()), 0, 500000)
    office = BytesIO()
    deck.save(office)
    members = {"first.pptx": office.getvalue(), "second.pptx": office.getvalue()}
    if container_kind == "mail":
        mail = EmailMessage()
        mail.set_content("α: attachments")
        for name, data in members.items():
            mail.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
        path = tmp_path / "pictures.eml"
        path.write_bytes(mail.as_bytes())
    else:
        path = tmp_path / "pictures.zip"
        raw = zip_bytes(members)
        path.write_bytes(zip_bytes({"inner.zip": raw}) if container_kind == "nested_zip" else raw)
    options = ExtractOptions(ocr="off")
    result = extract(path, options=options, out_dir=tmp_path / "cache")
    assert len(result.assets) == 2
    assert len({asset.asset_id for asset in result.assets}) == 2
    assert set(re.findall(r"asset:(ast_[a-f0-9]{24})", result.markdown)) == {a.asset_id for a in result.assets}
    blocks = {block.id: block for block in result.blocks}
    for asset in result.assets:
        assert asset.locator.unit == "member"
        assert AssetRecord(**asdict(asset)) == asset
        assert asset.block_ids
        assert any(f"asset:{asset.asset_id}" in result.markdown[blocks[b].start:blocks[b].end] for b in asset.block_ids)
    replay = extract(path, options=options, out_dir=tmp_path / "cache")
    assert replay.cache_hit and replay.assets == result.assets
    result.validate_contract()


def test_email_keeps_body_attachment_manifest_and_source_holds(tmp_path):
    mail = EmailMessage()
    mail["Subject"] = "Authored message"
    mail.set_content("Qualified body: only when x > 0.")
    mail.add_attachment(b"value\n", maintype="text", subtype="plain", filename="attachment.txt")
    mail.add_attachment(b"unknown", maintype="application", subtype="octet-stream", filename="object.bin")
    path = tmp_path / "mail.eml"
    path.write_bytes(mail.as_bytes())
    result = extract(path)
    assert "only when x > 0" in result.markdown and "value" in result.markdown
    assert result.status == "partial"
    assert len(result.metadata["container"]["members"]) == 3


def test_detached_binary_signature_cannot_become_body_text(tmp_path):
    path = tmp_path / "signature.p7s"
    path.write_bytes(b"\x30\x82\x00\x08opaque signature")
    result = extract(path)
    assert result.markdown == "" and result.status == "partial"
    assert any(i.code == "mail_body_unavailable" for i in result.issues)


def test_notebook_delegates_code_language_and_holds_outputs(tmp_path):
    pytest.importorskip("markitdown")
    path = tmp_path / "code.ipynb"
    path.write_text(json.dumps({"metadata": {"language_info": {"name": "julia"}}, "cells": [
        {"cell_type": "markdown", "source": ["# Source"]},
        {"cell_type": "code", "source": ["x = 2"], "outputs": [{"text": "2"}]}]}))
    result = extract(path)
    assert "```julia" in result.markdown and "x = 2" in result.markdown
    assert result.status == "partial"
    assert any(i.code == "notebook_outputs_omitted" for i in result.issues)
    assert all(b.source.unit == "document" for b in result.blocks)


def test_feed_uses_maintained_reader(tmp_path):
    pytest.importorskip("markitdown")
    path = tmp_path / "feed.rss"
    path.write_text('<rss version="2.0"><channel><title>Source</title><item><title>Entry</title><description>Qualified content</description></item></channel></rss>')
    result = extract(path)
    assert "Qualified content" in result.markdown
    result.validate_contract()


def test_epub_spine_content_is_retained_and_images_remain_held(tmp_path):
    pytest.importorskip("markitdown")
    path = tmp_path / "book.epub"
    path.write_bytes(zip_bytes({
        "mimetype": "application/epub+zip",
        "META-INF/container.xml": '<container><rootfiles><rootfile full-path="content.opf"/></rootfiles></container>',
        "content.opf": '<package xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata><dc:title>Book</dc:title></metadata><manifest><item id="chapter" href="chapter.xhtml"/></manifest><spine><itemref idref="chapter"/></spine></package>',
        "chapter.xhtml": '<html><body><h1>Chapter</h1><p>Qualified words</p></body></html>'}))
    result = extract(path)
    assert "Qualified words" in result.markdown and result.status == "partial"
    assert any(i.code == "epub_visual_content_unverified" for i in result.issues)


def test_heif_codec_is_explicit_and_untranscribed_content_is_partial(tmp_path):
    heif = pytest.importorskip("pillow_heif")
    image = pytest.importorskip("PIL.Image")
    heif.register_heif_opener()
    path = tmp_path / "image.heic"
    image.new("RGB", (32, 32), "white").save(path, format="HEIF")
    result = extract(path, options=ExtractOptions(ocr="off"))
    assert result.status == "partial" and result.blocks[0].source.unit == "frame"
    assert any(i.code == "image_text_unavailable" for i in result.issues)


@pytest.mark.parametrize("suffix,raw", [(".srt", "1\n00:00:01,000 --> 00:00:02,500\nQualified words\n"),
    (".vtt", "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nQualified words\n")])
def test_local_captions_have_exact_times(tmp_path, suffix, raw):
    pytest.importorskip("pysubs2")
    path = tmp_path / ("captions" + suffix)
    path.write_text(raw)
    result = extract(path)
    assert "[1–2.5s] Qualified words" in result.markdown
    assert result.metadata["captions"]["segments"][0]["end_seconds"] == 2.5
    assert result.review_status == "needs_review"


class AudioProvider:
    name, model_id, settings, cache_identity = "test", "test", {}, {"revision": "1"}
    modalities = {"audio"}

    def __init__(self, response=None):
        self.calls = []
        self.response = response or AIResponse("Source words", segments=[TranscriptSegment("Source\r\nwords", 1, 2)])

    def call(self, request):
        self.calls.append(request)
        assert isinstance(request.media[0], MediaAttachment)
        assert request.images == [] and request.task == "transcribe_audio"
        return self.response


def test_media_requires_explicit_modality_and_content_bound_cache(tmp_path):
    path = tmp_path / "authored.wav"
    path.write_bytes(b"audio fixture sent only to the deterministic double")
    with pytest.raises(ValueError, match="audio"):
        extract(path)
    provider = AudioProvider()
    result = extract(path, ai_provider=provider, out_dir=tmp_path / "out")
    assert len(provider.calls) == 1 and result.review_status == "needs_review"
    assert result.markdown[result.blocks[0].start:result.blocks[0].end] == "[1–2s] Source\nwords\n"
    assert extract(path, ai_provider=provider, out_dir=tmp_path / "out").cache_hit
    assert len(provider.calls) == 1
    assert result.metadata["ingestion"]["coverage"] == "transcript"


def test_bad_transcript_response_is_never_cached(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="segment"):
        extract(path, ai_provider=AudioProvider(AIResponse("bad", segments=[TranscriptSegment("bad", 3, 2)])), out_dir=tmp_path / "out")
    assert not list((tmp_path / "out").rglob("*.json"))


def test_url_retains_exact_bytes_and_does_not_reuse_another_origin(tmp_path, monkeypatch):
    import mdaddict.acquisition as acquisition
    raw = b"Original source\r\n"
    monkeypatch.setattr(acquisition, "_download", lambda source, **kw: (raw, source, {"content-type": "text/plain"}, []))
    for host in ("first.example", "second.example"):
        result = ingest(f"https://{host}/download", kind="url", allow_network=True, out_dir=tmp_path / "out")
        assert result.metadata["acquisition"]["origin"].startswith(f"https://{host}")
        assert result.metadata["ingestion"]["kind"] == "url"
        assert __import__("pathlib").Path(result.metadata["acquisition"]["raw_artifact"]["path"]).read_bytes() == raw
        saved = next(p for p in (tmp_path / "out").rglob("*.md") if p.stem == result.cache_key)
        assert load_extract(saved).metadata["acquisition"]["origin"].startswith(f"https://{host}")
    original = tmp_path / "download.txt"
    original.write_bytes(raw)
    local = extract(original, out_dir=tmp_path / "out")
    assert "acquisition" not in local.metadata and local.metadata["ingestion"]["kind"] == "file"


def test_specialized_page_uses_selected_reader_only(monkeypatch):
    pytest.importorskip("markitdown")
    import mdaddict.acquisition as acquisition
    raw = b'<html><h1 id="firstHeading">Authored title</h1><div id="mw-content-text"><p>Qualified source content</p></div></html>'
    monkeypatch.setattr(acquisition, "_download", lambda source, **kw: (raw, source, {"content-type": "text/html"}, []))
    result = ingest("https://en.wikipedia.org/wiki/Fixture", kind="url", allow_network=True)
    assert "Qualified source content" in result.markdown and "WikipediaConverter" in result.extractor


def test_dns_and_redirects_reject_private_targets(monkeypatch):
    import mdaddict.acquisition as acquisition
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))])
    with pytest.raises(ValueError, match="Private/local"):
        acquisition._download("https://example.com", options=ExtractOptions())
    with pytest.raises(ValueError, match="http"):
        acquisition._public_endpoint("file:///tmp/source")


def test_youtube_keeps_caption_times_and_holds_visuals(monkeypatch):
    import mdaddict.acquisition as acquisition
    from types import SimpleNamespace
    class Transcript(list):
        language, language_code, is_generated = "English", "en", True
    transcript = Transcript([SimpleNamespace(text="Condition", start=1.25, duration=2.5)])
    monkeypatch.setattr(acquisition, "_caption_client", lambda options: SimpleNamespace(fetch=lambda *a, **kw: transcript))
    result = ingest("abcdefghijk", kind="youtube", allow_network=True)
    assert result.markdown == "[1.25–3.75s] Condition\n"
    assert result.status == "partial" and result.metadata["acquisition"]["is_generated"]
    assert result.metadata["acquisition_identity"]["implementation"]
    artifact = result.metadata["acquisition"]["raw_artifact"]
    payload = json.loads(base64.b64decode(artifact["data"]))
    assert payload["snippets"][0]["start_seconds"] == 1.25


def test_xls_meaningful_content_and_cache_limits(tmp_path):
    pytest.importorskip("markitdown")
    pytest.importorskip("xlrd")
    path = tmp_path / "sheet.xls"
    path.write_bytes(xls_bytes("AuthoredSheet", [[42.5, 100.0], [3.14, 0.0]]))
    result = extract(path)
    assert "AuthoredSheet" in result.markdown
    assert "42.5" in result.markdown and "100.0" in result.markdown and "3.14" in result.markdown
    assert result.status == "partial"
    assert any(i.code == "xls_cached_values_unverified" for i in result.issues)

    # Cell budget enforcement
    with pytest.raises(ValueError, match="max_cells"):
        extract(path, options=ExtractOptions(max_cells=2))

    # Malformed XLS
    malformed = tmp_path / "bad.xls"
    malformed.write_bytes(b"\xd0\xcf\x11\xe0corrupt ole file")
    with pytest.raises(Exception):
        extract(malformed)


def test_msg_binary_meaningful_content_and_omissions(tmp_path):
    pytest.importorskip("markitdown")
    pytest.importorskip("olefile")
    msg_data = ole_bytes({
        "__properties_version1.0": b"\x00" * 32,
        "__recip_version1.0_#00000000": b"\x00",
        "__substg1.0_0037001F": "Lab Progress Report".encode("utf-16le"),
        "__substg1.0_0C1F001F": "researcher@example.com".encode("utf-16le"),
        "__substg1.0_0E04001F": "team@example.com".encode("utf-16le"),
        "__substg1.0_1000001F": "Qualified measurement: output is 42.5 W when input >= 10.0 V.".encode("utf-16le"),
    })
    path = tmp_path / "report.msg"
    path.write_bytes(msg_data)
    result = extract(path)
    assert "Lab Progress Report" in result.markdown
    assert "researcher@example.com" in result.markdown
    assert "42.5 W" in result.markdown and "10.0 V" in result.markdown
    assert result.status == "partial"
    assert any(i.code == "mail_attachments_unconverted" for i in result.issues)
    assert not any(i.code == "mail_body_unavailable" for i in result.issues)

    # Empty body MSG reports mail_body_unavailable
    empty_msg = ole_bytes({
        "__properties_version1.0": b"\x00" * 32,
        "__recip_version1.0_#00000000": b"\x00",
        "__substg1.0_0037001F": "Headers Only".encode("utf-16le"),
        "__substg1.0_0C1F001F": "a@example.com".encode("utf-16le"),
    })
    empty_path = tmp_path / "empty.msg"
    empty_path.write_bytes(empty_msg)
    res_empty = extract(empty_path)
    assert any(i.code == "mail_body_unavailable" for i in res_empty.issues)
    assert any(i.code == "mail_attachments_unconverted" for i in res_empty.issues)


def test_atom_feed_meaningful_content(tmp_path):
    pytest.importorskip("markitdown")
    atom_xml = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Physics News</title>
  <entry>
    <title>Quantum Discovery</title>
    <summary>Qualified result: efficiency reached 98.5% under pressure = 2.0 atm.</summary>
  </entry>
</feed>"""
    path = tmp_path / "feed.atom"
    path.write_text(atom_xml, encoding="utf-8")
    result = extract(path)
    assert "Physics News" in result.markdown or "Quantum Discovery" in result.markdown
    assert "98.5%" in result.markdown
    result.validate_contract()


def test_capabilities_reflect_options_and_markitdown_version(monkeypatch):
    from importlib import metadata
    from importlib.util import find_spec
    from mdaddict import MissingDependencyError
    from mdaddict.delegated import _markitdown_reader

    # options.ocr == "off" does not require tesseract for image
    caps_off = capabilities(options=ExtractOptions(ocr="off"))
    img_cap_off = next(c for c in caps_off if c.id == "image")
    assert "tool:tesseract" not in img_cap_off.missing
    assert img_cap_off.availability == ("ready" if find_spec("PIL") is not None else "missing_dependency")

    # options.ocr == "auto" or "force" checks tesseract
    monkeypatch.setattr("shutil.which", lambda tool: None if tool == "tesseract" else "/bin/" + tool)
    caps_auto = capabilities(options=ExtractOptions(ocr="auto"))
    img_cap_auto = next(c for c in caps_auto if c.id == "image")
    assert "tool:tesseract" in img_cap_auto.missing
    assert img_cap_auto.availability == "missing_dependency"

    # options.pdf_backend selection
    caps_pdfium = capabilities(options=ExtractOptions(pdf_backend="pdfium"))
    assert next(c for c in caps_pdfium if c.id == "pdf").availability in {"ready", "missing_dependency"}

    if find_spec("markitdown") is not None:
        # Wrong markitdown version reporting
        monkeypatch.setattr(metadata, "version", lambda pkg: "0.2.0" if pkg == "markitdown" else "1.0.0")
        caps_ver = capabilities()
        xls_cap = next(c for c in caps_ver if c.id == "xls")
        assert "module:markitdown==0.1.9" in xls_cap.missing
        assert xls_cap.availability == "missing_dependency"

        # Reader raises MissingDependencyError on wrong version
        with pytest.raises(MissingDependencyError, match="0.1.9"):
            _markitdown_reader(".xls")
    else:
        caps_ver = capabilities()
        xls_cap = next(c for c in caps_ver if c.id == "xls")
        assert "module:markitdown" in xls_cap.missing
        assert xls_cap.availability == "missing_dependency"


@pytest.mark.parametrize("ocr", ["off", "auto", "force"])
def test_office_and_pdf_capabilities_account_for_forced_ocr(monkeypatch, ocr):
    monkeypatch.setattr("shutil.which", lambda name: None if name == "tesseract" else "/bin/" + name)
    rows = {row.id: row for row in capabilities(options=ExtractOptions(ocr=ocr))}
    for family in ("pdf", "docx", "pptx", "legacy-office"):
        assert ("tool:tesseract" in rows[family].missing) == (ocr == "force")
        if ocr == "force":
            assert rows[family].availability == "missing_dependency"


def test_soffice_discovery_and_aliases(monkeypatch):
    from mdaddict.legacy import find_soffice
    # Neither libreoffice nor soffice
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setenv("PROGRAMFILES", "")
    monkeypatch.setenv("PROGRAMFILES(X86)", "")
    assert find_soffice() is None

    # libreoffice on PATH
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/libreoffice" if name == "libreoffice" else None)
    assert find_soffice() == "/usr/bin/libreoffice"

    # soffice on PATH
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/soffice" if name == "soffice" else None)
    assert find_soffice() == "/usr/bin/soffice"

