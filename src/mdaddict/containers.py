"""Bounded offline ZIP/mail traversal with a shared recursive budget.

Member bytes are written under generated temporary names, never archive paths.
Child results retain their own hashes/locators in metadata; parent spans point
to the exact embedded child Markdown. Context variables isolate concurrent jobs.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from email import policy
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile

from .strategy import (ExtractOptions, ExtractResult, ExtractionIssue, SourceBlock,
                       SourceLocator, normalize, sha256_file)


class ContainerLimitError(ValueError):
    """A complete container cannot be read within its declared job budget."""


@dataclass
class _Budget:
    max_members: int
    max_bytes: int
    max_depth: int
    members: int = 0
    expanded_bytes: int = 0

    def reserve(self, size):
        if self.members + 1 > self.max_members:
            raise ContainerLimitError(f"Container exceeds max_archive_members={self.max_members}")
        if size < 0 or self.expanded_bytes + size > self.max_bytes:
            raise ContainerLimitError(f"Container exceeds max_expanded_mb budget ({self.max_bytes} bytes)")
        self.members += 1
        self.expanded_bytes += size


_BUDGET: ContextVar[_Budget | None] = ContextVar("mdaddict_container_budget", default=None)
_DEPTH: ContextVar[int] = ContextVar("mdaddict_container_depth", default=0)


@contextmanager
def _scope(options):
    current = _BUDGET.get()
    token = None
    if current is None:
        current = _Budget(getattr(options, "max_archive_members", 200),
            getattr(options, "max_expanded_mb", 500) * 1024 * 1024,
            getattr(options, "max_archive_depth", 3))
        token = _BUDGET.set(current)
    depth = _DEPTH.get() + 1
    if depth > current.max_depth:
        if token is not None:
            _BUDGET.reset(token)
        raise ContainerLimitError(f"Container exceeds max_archive_depth={current.max_depth} (root container is depth 1)")
    depth_token = _DEPTH.set(depth)
    try:
        yield current
    finally:
        _DEPTH.reset(depth_token)
        if token is not None:
            _BUDGET.reset(token)


def check_zip_budget(path: Path, options: ExtractOptions):
    """Preflight ZIP-backed EPUB readers before third-party decompression."""
    with _scope(options) as budget, zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if not entry.is_dir():
                budget.reserve(entry.file_size)


class _Assembly:
    def __init__(self, path, kind):
        self.path, self.kind = path, kind
        self.parts, self.blocks, self.issues, self.members = [], [], [], []
        self.length = 0

    def append(self, text):
        start = self.length
        self.parts.append(text)
        self.length += len(text)
        return start

    def issue(self, code, message, index=1, block_ids=()):
        self.issues.append(ExtractionIssue(code, message, SourceLocator("member", index), list(block_ids), "unresolved"))

    def child(self, record, data, options):
        record.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        self.members.append(record)
        index = record["index"]
        try:
            suffix = PurePosixPath(record["path"].replace("\\", "/")).suffix.lower()
            if not re.fullmatch(r"\.[a-z0-9]{1,16}", suffix):
                suffix = ".bin"
            with tempfile.TemporaryDirectory(prefix="mdaddict-member-") as temporary:
                member_path = Path(temporary) / ("member" + suffix)
                member_path.write_bytes(data)
                from .extract import extract
                result = extract(member_path, options=options)
            record.update(status=result.status, extractor=result.extractor,
                review_status=result.review_status, source_blocks=[asdict(b) for b in result.blocks],
                issues=[asdict(i) for i in result.issues], metadata=result.metadata)
            self.append(f"\n\n### {self.kind.capitalize()} member {index}\n\n")
            offset = self.append(result.markdown)
            mapping = {b.id: f"member-{index}:{b.id}" for b in result.blocks}
            for block in result.blocks:
                locator = SourceLocator("member", index, json.dumps(
                    {"path": record["path"], "source": asdict(block.source)}, ensure_ascii=False, sort_keys=True))
                self.blocks.append(SourceBlock(mapping[block.id], block.kind, locator,
                    offset + block.start, offset + block.end, block.method))
            for issue in result.issues:
                self.issues.append(ExtractionIssue(issue.code, issue.message,
                    SourceLocator("member", index, record["path"]),
                    [mapping[b] for b in issue.block_ids], issue.severity))
            if not result.markdown.strip():
                self.issue("container_member_empty", "A member produced no body content; see the member manifest.", index)
            if result.status == "failure":
                self.issue("container_member_failed", "A member reader reported failure; see the member manifest.", index)
        except Exception as exc:
            record.update(status="failure", error_type=type(exc).__name__, error=str(exc)[:2000])
            self.issue("container_member_failed", f"Member {index} could not be converted: {type(exc).__name__}: {str(exc)[:500]}", index)

    def result(self, budget):
        if not self.members:
            self.issue("container_no_members", "The container has no converted member body content.")
        result = ExtractResult(sha256_file(self.path), "".join(self.parts), self.path.name,
            "offline-" + self.kind, pages=1, blocks=self.blocks, issues=self.issues,
            usage={"requests": 0}, metadata={"container": {"revision": 1, "kind": self.kind,
                "members": self.members, "member_count_used": budget.members,
                "expanded_bytes_used": budget.expanded_bytes, "root_depth": 1,
                "provenance": "original container hash, member path/hash and original child locators"}})
        result.refresh_status()
        return result


def _extract_zip(path, options):
    with _scope(options) as budget, zipfile.ZipFile(path) as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        # Reject over-budget directory metadata before any member conversion.
        if budget.members + len(entries) > budget.max_members:
            raise ContainerLimitError(f"Container exceeds max_archive_members={budget.max_members}")
        if budget.expanded_bytes + sum(e.file_size for e in entries) > budget.max_bytes:
            raise ContainerLimitError(f"Container exceeds max_expanded_mb budget ({budget.max_bytes} bytes)")
        output = _Assembly(path, "archive")
        for index, entry in enumerate(entries, 1):
            record = {"index": index, "path": entry.filename, "sha256": None}
            try:
                budget.reserve(entry.file_size)
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError("Archive symlink members are not followed")
                with archive.open(entry) as stream:
                    data = stream.read(entry.file_size + 1)
                if len(data) != entry.file_size:
                    raise ValueError("Archive member size differs from its declared size")
            except Exception as exc:
                record.update(status="failure", error_type=type(exc).__name__, error=str(exc)[:2000],
                    hash_status="unavailable: member was not read completely")
                output.members.append(record)
                output.issue("container_member_failed", f"Member {index} could not be read: {str(exc)[:500]}", index)
                continue
            output.child(record, data, options)
        return output.result(budget)


def _extract_email(path, options):
    with _scope(options) as budget:
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        output = _Assembly(path, "mail")
        if path.suffix.lower() == ".p7s" and not list(message.keys()):
            output.issue("mail_body_unavailable", "Detached binary P7S signatures contain no readable mail body; no binary bytes were treated as text.")
            output.issue("mail_signature_unverified", "Cryptographic signatures were not validated.")
            return output.result(budget)
        headers = "\n".join(f"{name}: {' '.join(str(message[name]).splitlines())}"
            for name in ("From", "To", "Cc", "Date", "Subject") if message[name] is not None)
        if headers:
            start = output.append(normalize(headers) + "\n")
            output.blocks.append(SourceBlock("mail-headers", "metadata", SourceLocator("message", 1, "headers"), start, output.length))
        body = message.get_body(preferencelist=("plain", "html"))
        alternatives = [part for part in message.walk() if part is not body and part.get_content_type() in {"text/plain", "text/html"}
                        and part.get_content_disposition() != "attachment"]
        if alternatives:
            output.issue("mail_alternative_body_unverified", "An alternative plain/HTML body was not selected; inspect the original message for differences.")
        if body is not None:
            data = body.get_payload(decode=True) or b""
            budget.reserve(len(data))
            if body.get_content_type() == "text/plain":
                try:
                    text = data.decode(body.get_content_charset() or "utf-8")
                except (UnicodeError, LookupError):
                    text = data.decode("utf-8", errors="replace")
                    output.issue("mail_encoding_unresolved", "The mail body could not be decoded losslessly using its declared encoding.")
                start = output.append(normalize(text))
                output.blocks.append(SourceBlock("mail-body", "text", SourceLocator("message", 1, "text/plain"), start, output.length))
                output.members.append({"index": 1, "path": "body.txt", "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data), "status": "success", "kind": "body"})
            else:
                output.child({"index": 1, "path": "body.html", "kind": "body"}, data, options)
        else:
            output.issue("mail_body_unavailable", "No readable plain-text or HTML mail body was found; metadata alone is incomplete.")
        if message.get_content_type() == "multipart/signed" or path.suffix.lower() == ".p7s":
            output.issue("mail_signature_unverified", "Cryptographic signatures were not validated; a detached P7S signature alone contains no readable mail body.")
        for attachment in message.iter_attachments():
            index = len(output.members) + 1
            name = attachment.get_filename() or f"attachment-{index}"
            if attachment.get_content_type() == "message/rfc822":
                payload = attachment.get_payload()
                data = payload[0].as_bytes(policy=policy.default) if isinstance(payload, list) and payload else b""
                if not name.lower().endswith(".eml"):
                    name += ".eml"
            else:
                data = attachment.get_payload(decode=True) or b""
            try:
                budget.reserve(len(data))
            except ContainerLimitError as exc:
                output.members.append({"index": index, "path": name, "sha256": None,
                    "status": "failure", "error_type": type(exc).__name__, "error": str(exc),
                    "hash_status": "unavailable: resource budget exceeded"})
                output.issue("container_budget_exceeded", str(exc), index)
                break
            output.child({"index": index, "path": name, "kind": "attachment"}, data, options)
        result = output.result(budget)
        if body is not None and not any(b.kind != "metadata" and result.markdown[b.start:b.end].strip() for b in result.blocks):
            output.issue("mail_body_empty", "The mail body is empty; headers are not body content.")
            result = output.result(budget)
        return result


def extract_container(path: Path, options: ExtractOptions) -> ExtractResult:
    """Read local ZIP or MIME email. Recursive public calls inherit this job's limits."""
    path = Path(path)
    if path.suffix.lower() == ".zip":
        return _extract_zip(path, options)
    if path.suffix.lower() in {".eml", ".p7s"}:
        return _extract_email(path, options)
    raise ValueError(f"Unsupported container type {path.suffix!r}")
