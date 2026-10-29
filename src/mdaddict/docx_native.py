"""Let Pandoc translate Word; carry original XML paragraph anchors through it.

Markers exist only in a job-owned copy. Their boundaries are removed after image
handling, leaving source spans even for duplicate paragraphs, lists and cells.
"""
from __future__ import annotations

from html.parser import HTMLParser
from copy import copy
from bisect import bisect_right
from collections import defaultdict, deque
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile

from mdaddict.strategy import ExtractionIssue, SourceBlock, SourceLocator, normalize

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def convert_docx(engine, path):
    from lxml import etree
    if not shutil.which("pandoc"):
        raise RuntimeError("Pandoc is required for DOCX. Install it or use the Docker image.")
    prefix = "MDADDICT" + uuid.uuid4().hex.upper()
    anchors = {}
    contexts = {}
    image_crops = defaultdict(deque)
    pending_issues = []
    mixed_blocks = set()
    marker = re.compile(prefix + r"(\d+)(B|E)Z")

    def record(code, message, source, block_id=None, severity="unresolved"):
        engine.warn(message)
        pending_issues.append(ExtractionIssue(code, message, source, [block_id] if block_id else [], severity))

    with zipfile.ZipFile(path) as original, tempfile.TemporaryDirectory(prefix="mdaddict-docx-") as directory:
        marked_path = Path(directory) / "marked.docx"
        with zipfile.ZipFile(marked_path, "w", compression=zipfile.ZIP_DEFLATED) as marked:
            for info in original.infolist():
                data = original.read(info)
                if info.filename in {"word/document.xml", "word/footnotes.xml", "word/endnotes.xml"}:
                    root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
                    rel_name = posixpath.join(posixpath.dirname(info.filename), "_rels", posixpath.basename(info.filename) + ".rels")
                    relationships = {}
                    if rel_name in original.namelist():
                        rel_root = etree.fromstring(original.read(rel_name), etree.XMLParser(resolve_entities=False, no_network=True))
                        relationships = {node.get("Id"): posixpath.normpath(posixpath.join(posixpath.dirname(info.filename), node.get("Target", "")))
                                         for node in rel_root if node.get("TargetMode") != "External"}
                    cells = root.findall(f".//{{{W}}}tc")
                    if cells:
                        engine.check_cells(len(cells))
                    paragraphs = root.findall(f".//{{{W}}}p")
                    context_texts = ["".join(p.xpath(".//w:t/text()",namespaces={"w":W})) for p in paragraphs]
                    for at, para in enumerate(paragraphs):
                        if any(parent.tag in {f"{{{W}}}footnote", f"{{{W}}}endnote"} and
                               parent.get(f"{{{W}}}type") in {"separator", "continuationSeparator", "continuationNotice"}
                               for parent in para.iterancestors()):
                            continue
                        # A paragraph under a nested drawing is not guaranteed to be read.
                        if not any(c.tag != f"{{{W}}}pPr" for c in para):
                            continue
                        element = info.filename + ":" + root.getroottree().getpath(para)
                        source = SourceLocator("document", 1, element)
                        block_id = "docx:" + element
                        key = str(len(anchors))
                        contexts[key] = "\n".join(context_texts[max(0,at-1):at+3])
                        anchors[key] = (source, block_id)
                        # Pandoc consumes Title/Subtitle paragraphs as document
                        # metadata and omits their marked content from Markdown.
                        # Change style only in this job-owned copy so title text
                        # retains the original XML paragraph locator and span.
                        style = para.find(f"{{{W}}}pPr/{{{W}}}pStyle")
                        if style is not None and style.get(f"{{{W}}}val") in {"Title", "Subtitle"}:
                            style.set(f"{{{W}}}val", "Normal")
                        for side in ("B", "E"):
                            run = etree.Element(f"{{{W}}}r")
                            text = etree.SubElement(run, f"{{{W}}}t")
                            text.text = prefix + key + side + "Z"
                            if side == "B":
                                para.insert(1 if len(para) and para[0].tag == f"{{{W}}}pPr" else 0, run)
                            else:
                                para.append(run)
                        if para.findall(f".//{{{W}}}object") or para.findall(f".//{{{W}}}pict"):
                            record("docx_object_unresolved", f"{element}: legacy/embedded object requires review", source, block_id)
                        for drawing in para.findall(f".//{{{W}}}drawing"):
                            if not drawing.findall(f".//{{{A}}}blip"):
                                record("docx_drawing_unresolved", f"{element}: drawing has no supported raster image", source, block_id)
                            for blip in drawing.findall(f".//{{{A}}}blip"):
                                target = relationships.get(blip.get(f"{{{R}}}embed"))
                                if target:
                                    rect = blip.getparent().find(f"{{{A}}}srcRect")
                                    crop = tuple(float(rect.get(edge, "0")) / 100_000 if rect is not None else 0.
                                                 for edge in ("l", "t", "r", "b"))
                                    image_crops[(key, target)].append(crop)
                    for tag in ("altChunk", "del", "ins"):
                        if root.findall(f".//{{{W}}}{tag}"):
                            record("docx_source_feature_review", f"{info.filename}: {tag} content requires review", SourceLocator(), severity="unresolved")
                    if root.findall(f".//{{{W}}}gridSpan") or root.findall(f".//{{{W}}}vMerge"):
                        record("docx_table_spans_review", f"{info.filename}: merged table cells require grid review", SourceLocator(), severity="review")
                    data = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
                elif re.fullmatch(r"word/(?:header\d+|footer\d+|comments)\.xml", info.filename):
                    root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
                    if any(root.itertext()):
                        record("docx_part_unresolved", f"{info.filename}: header/footer/comments not included by this adapter", SourceLocator())
                # ZipFile.writestr mutates ZipInfo offsets; keep the source archive's
                # entries intact for lazy image reads later in this job.
                marked.writestr(copy(info), data)
        # Disable GFM's code-span/fence math convention: downstream consumers
        # use dollar math, and code wrappers can escape a closing delimiter.
        run = subprocess.run(["pandoc", "--sandbox", "--wrap=none", "-f", "docx", "-t", "gfm+tex_math_dollars-tex_math_gfm", str(marked_path)],
            encoding="utf-8", capture_output=True, timeout=engine.options.timeout)
        if run.returncode:
            raise RuntimeError("Pandoc failed: " + run.stderr[-500:])
        if run.stderr.strip():
            engine.warn("Pandoc: " + run.stderr.strip()[:500])
        body = re.sub(r"\$`+([^`\n]+)`+\$", r"$\1$", run.stdout)
        positions, owners, active = [], [], []
        for boundary in marker.finditer(body):
            key, side = boundary.groups()
            if side == "B":
                active.append(key)
            elif key in active:
                active.remove(key)
            positions.append(boundary.end())
            owners.append(active[-1] if active else None)

        def replace_image(match):
            if match.group("html"):
                class Attributes(HTMLParser):
                    def handle_starttag(self, tag, attrs):
                        self.attrs = dict(attrs)
                parser = Attributes()
                parser.feed(match.group())
                target, alt = parser.attrs.get("src", ""), parser.attrs.get("alt", "")
            else:
                target, alt = match.group("target").strip("<>"), match.group("alt")
            index = bisect_right(positions, match.start()) - 1
            owner = owners[index] if index >= 0 else None
            source, block_id = anchors[owner] if owner is not None else (SourceLocator(), None)
            member = "word/" + target
            data = original.read(member) if member in original.namelist() else None
            crops = image_crops.get((owner, member))
            crop = crops.popleft() if crops else (0., 0., 0., 0.)
            passage = engine.image_evidence.describe(engine, data, alt, source.element or f"image {target}", source, block_id, crop=crop, context=contexts.get(owner,""))
            if passage.method != "native" and block_id is not None:
                mixed_blocks.add(block_id)
            for message in passage.messages:
                record(passage.code, message, source, block_id,
                       "unresolved" if passage.method == "native" else "review")
            return passage.text

        body = re.sub(r"(?P<html><img\b[^>]*>)|!\[(?P<alt>[^\]]*)\]\((?P<target>[^)]+)\)(?:\{[^}]*\})?", replace_image, body, flags=re.I)

    body = normalize(body)
    pieces, starts, ends = [], {}, {}
    cursor = length = 0
    for boundary in marker.finditer(body):
        text = body[cursor:boundary.start()]
        pieces.append(text)
        length += len(text)
        key, side = boundary.groups()
        slots = starts if side == "B" else ends
        if key in slots:
            raise RuntimeError("Pandoc duplicated a DOCX source boundary")
        slots[key] = length
        cursor = boundary.end()
    pieces.append(body[cursor:])
    output = "".join(pieces)
    for key, (source, block_id) in anchors.items():
        if key not in starts or key not in ends or ends[key] < starts[key]:
            record("docx_paragraph_unresolved", f"{source.element}: paragraph boundary lost during conversion", source)
            continue
        engine.source_blocks.append(SourceBlock(block_id, "paragraph", source, starts[key], ends[key],
                                               "mixed" if block_id in mixed_blocks else "native"))
    available = {b.id for b in engine.source_blocks}
    for problem in pending_issues:
        problem.block_ids = [key for key in problem.block_ids if key in available]
        engine.issues.append(problem)
    return output
