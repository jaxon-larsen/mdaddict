"""Opt-in URL/caption acquisition with bounded, public-address-only HTTP."""
from __future__ import annotations

import base64
import hashlib
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

from .strategy import ExtractOptions, ExtractResult, ExtractionIssue, SourceBlock, SourceLocator


def _public_endpoint(url: str):
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Acquisition requires an http(s) URL without credentials")
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise ValueError("Control characters are not allowed in URLs")
    host = parts.hostname.encode("idna").decode("ascii")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if host.lower() == "localhost" or host.lower().endswith((".localhost", ".local")):
        raise ValueError("Private/local URL targets are not allowed")
    answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or any(not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast for address in addresses):
        raise ValueError("Private/local URL targets are not allowed")
    return parts, host, port, addresses[0]


def _request_once(url, endpoint, *, deadline, maximum, method="GET", data=None, headers=None):
    parts, host, port, address = endpoint
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Acquisition time budget exhausted")
    cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    connection = cls(host, port=port, timeout=remaining)
    # Keep the original host for HTTP Host and TLS certificate/SNI validation,
    # while connecting to the already-vetted IP instead of resolving it again.
    connection._create_connection = lambda _target, timeout, source_address=None: socket.create_connection(
        (address, port), timeout, source_address)
    try:
        request_headers = {"User-Agent": "mdaddict/explicit-acquisition", **(headers or {}), "Accept-Encoding": "identity"}
        path = urlunsplit(("", "", parts.path or "/", parts.query, ""))
        connection.request(method, path, body=data, headers=request_headers)
        response = connection.getresponse()
        response_headers = dict(response.getheaders())
        length = response.getheader("Content-Length")
        if length and (not length.isdigit() or int(length) > maximum):
            raise ValueError("Remote artifact exceeds the acquisition byte limit")
        if response.getheader("Content-Encoding", "identity").lower() not in {"identity", ""}:
            raise ValueError("Compressed HTTP transport is not accepted; no expansion was attempted")
        content = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Acquisition time budget exhausted")
            if connection.sock:
                connection.sock.settimeout(remaining)
            chunk = response.read(min(65536, maximum + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > maximum:
                raise ValueError("Remote artifact exceeds the acquisition byte limit")
        return response.status, response_headers, bytes(content)
    finally:
        connection.close()


def _download(url, *, options, method="GET", data=None, headers=None, deadline=None, maximum=None):
    deadline = deadline if deadline is not None else time.monotonic() + options.timeout
    maximum = maximum if maximum is not None else options.max_mb * 1024 * 1024
    redirects = []
    for _ in range(6):
        endpoint = _public_endpoint(url)
        status, response_headers, content = _request_once(url, endpoint, deadline=deadline, maximum=maximum,
                                                         method=method, data=data, headers=headers)
        lower = {key.lower(): value for key, value in response_headers.items()}
        if status in {301, 302, 303, 307, 308}:
            if "location" not in lower:
                raise ValueError("Remote redirect has no Location")
            redirects.append(url)
            target = urljoin(url, lower["location"])
            if urlsplit(target).netloc.lower() != urlsplit(url).netloc.lower():
                headers = {key: value for key, value in (headers or {}).items() if key.lower() not in {"cookie", "authorization"}}
            url = target
            if status == 303 or (status in {301, 302} and method == "POST"):
                method, data = "GET", None
            continue
        if not 200 <= status < 300:
            raise ValueError(f"Remote acquisition failed with HTTP {status}")
        return content, url, lower, redirects
    raise ValueError("Acquisition exceeded five redirects")


def _retain(raw: bytes, name: str, out_dir):
    digest = hashlib.sha256(raw).hexdigest()
    details = {"sha256": digest, "bytes": len(raw)}
    if out_dir is None:
        return {**details, "encoding": "base64", "data": base64.b64encode(raw).decode("ascii")}
    destination = Path(out_dir).resolve() / ".sources" / digest / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".acquire-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {**details, "path": str(destination)}


def _video_id(source: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", source):
        return source
    parts = urlsplit(source)
    if parts.scheme not in {"http", "https"} or parts.username or parts.password:
        raise ValueError("Supply a YouTube video ID or http(s) YouTube URL")
    host = (parts.hostname or "").lower()
    if host in {"youtu.be", "www.youtu.be"}:
        identity = parts.path.strip("/")
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        identity = parse_qs(parts.query).get("v", [""])[0] if parts.path == "/watch" else parts.path.split("/")[-1] if parts.path.startswith(("/shorts/", "/embed/", "/live/")) else ""
    else:
        identity = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", identity):
        raise ValueError("A supported YouTube URL or 11-character video ID is required")
    return identity


def _caption_client(options):
    try:
        import requests
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as error:
        raise RuntimeError("YouTube captions require mdaddict[online] (youtube-transcript-api 1.2.x)") from error
    deadline = time.monotonic() + options.timeout

    class BoundedSession(requests.Session):
        def __init__(self):
            super().__init__()
            self.remaining_bytes = options.max_mb * 1024 * 1024

        def request(self, method, url, **kwargs):
            request_headers = {**self.headers, **kwargs.get("headers", {})}
            body = json.dumps(kwargs["json"]).encode() if "json" in kwargs else kwargs.get("data")
            if "json" in kwargs:
                request_headers["Content-Type"] = "application/json"
            prepared = requests.Request(method, url).prepare()
            cookie = requests.cookies.get_cookie_header(self.cookies, prepared)
            if cookie:
                request_headers["Cookie"] = cookie
            raw, final, headers, _ = _download(url, options=options, method=method.upper(), data=body,
                headers=request_headers, deadline=deadline, maximum=self.remaining_bytes)
            self.remaining_bytes -= len(raw)
            response = requests.Response()
            response.status_code, response.url, response.headers = 200, final, headers
            response._content, response.encoding = raw, "utf-8"
            return response

    return YouTubeTranscriptApi(http_client=BoundedSession())


def _youtube(source, options, out_dir):
    identity = _video_id(source)
    languages = [{"eng": "en", "deu": "de", "fra": "fr", "spa": "es"}.get(lang, lang)
                 for lang in options.language.split("+")]
    try:
        transcript = _caption_client(options).fetch(identity, languages=languages)
    except (ValueError, RuntimeError, TimeoutError):
        raise
    except Exception as error:
        raise RuntimeError(f"YouTube captions unavailable ({type(error).__name__}); no translation or audio fallback attempted") from error
    segments, chunks, blocks, offset = [], [], [], 0
    for index, snippet in enumerate(transcript, 1):
        begin, duration = snippet.start, snippet.duration
        if (index > options.max_cells or not isinstance(snippet.text, str) or not snippet.text.strip()
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 for value in (begin, duration))):
            raise ValueError("Invalid or oversized YouTube caption transcript")
        from .strategy import normalize
        chunk = normalize(f"[{begin:g}–{begin + duration:g}s] {snippet.text}")
        chunks.append(chunk)
        blocks.append(SourceBlock(f"caption:{index}", "transcript", SourceLocator("recording", 1, f"seconds:{begin:g}-{begin+duration:g}"), offset, offset + len(chunk), "native"))
        segments.append({"text": snippet.text, "start_seconds": begin, "duration_seconds": duration})
        offset += len(chunk)
    if not chunks:
        raise ValueError("YouTube captions unavailable or empty; metadata alone is not an extraction")
    payload = {"video_id": identity, "language": transcript.language, "language_code": transcript.language_code,
               "is_generated": transcript.is_generated, "snippets": segments}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    if len(raw) > options.max_mb * 1024 * 1024:
        raise ValueError("YouTube caption artifact exceeds max_mb")
    artifact = _retain(raw, "captions.json", out_dir)
    issues = [ExtractionIssue("youtube_caption_review", "Captions are not independently verified against the recording", SourceLocator("recording", 1), [b.id for b in blocks], "review"),
              ExtractionIssue("youtube_visual_unprocessed", "Only existing captions were acquired; video frames and visual relationships were not processed", SourceLocator("recording", 1), [b.id for b in blocks], "unresolved")]
    result = ExtractResult(hashlib.sha256(raw).hexdigest(), "".join(chunks), identity, "youtube:captions", blocks=blocks, issues=issues,
        metadata={"acquisition": {"kind": "youtube", "origin": f"https://www.youtube.com/watch?v={identity}", "raw_artifact": artifact,
                    "raw_artifact_kind": "structured caption API response; not the video or original caption XML", **payload}})
    result.refresh_status()
    return result


def acquire(source: str, *, kind: str, allow_network: bool, options: ExtractOptions,
            ai_provider=None, out_dir=None, force=False) -> ExtractResult:
    """Fetch only after explicit opt-in; URLs are artifact snapshots, not crawls."""
    if kind not in {"url", "youtube"}:
        raise ValueError("Acquisition kind must be 'url' or 'youtube'")
    if not allow_network:
        raise ValueError("Remote acquisition requires allow_network=True")
    if kind == "youtube":
        return _youtube(source, options, out_dir)
    raw, final_url, headers, redirects = _download(source, options=options)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(unquote(urlsplit(final_url).path)).name).strip(".") or "download"
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    suffixes = {"text/html": ".html", "application/xhtml+xml": ".html", "text/plain": ".txt", "application/pdf": ".pdf"}
    from .capabilities import capability_for
    if capability_for(name) is None:
        capability = capability_for(name, content_type)
        suffix = suffixes.get(content_type) or (capability.extensions[0] if capability and capability.extensions else "")
        if suffix:
            name = "download" + suffix
    name = "download-" + name[:120]
    if not raw:
        raise ValueError("Remote artifact is empty; metadata alone is not an extraction")
    artifact = _retain(raw, name, out_dir)
    from .extract import extract
    with tempfile.TemporaryDirectory(prefix="mdaddict-url-") as directory:
        path = Path(directory) / name
        path.write_bytes(raw)
        result = None
        if content_type in {"text/html", "application/xhtml+xml"}:
            from .delegated import extract_web_snapshot
            result = extract_web_snapshot(path, options, final_url)
        if result is None:
            result = extract(path, options=options, ai_provider=ai_provider, out_dir=out_dir, force=force)
    result.metadata["acquisition"] = {"kind": "url", "origin": source, "final_url": final_url,
        "redirects": redirects, "content_type": content_type, "raw_artifact": artifact,
        "scope": "Downloaded artifact only; linked resources and dynamic scripts were not retrieved or executed"}
    if content_type in {"text/html", "application/xhtml+xml"}:
        result.issues.append(ExtractionIssue("url_snapshot_review", "Static downloaded HTML snapshot; dynamic and linked content were not acquired",
            SourceLocator("document", 1), [b.id for b in result.blocks], "review"))
        result.refresh_status()
    return result
