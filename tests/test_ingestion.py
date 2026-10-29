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
