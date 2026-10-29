"""Conservative paragraph permutation for simple numbered PDF columns.

Reuse the existing slide ordering proof. Never regenerate text or infer an
arbitrary layout: the complete source/Markdown paragraph mapping must be unique.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from mdaddict.reading_order import order_shapes


@dataclass(frozen=True)
class _TextRegion:
    shape_id: int
    text: str
    left: float
    top: float
    width: float
    height: float
    rotation: float = 0
    has_text_frame: bool = True


def _paragraph_key(text: str, *, markdown=False, ignored="") -> str:
    if markdown:
        text = re.sub(r"(?m)^ {0,3}#{1,6}\s+", "", text.strip())
        # Ignore emphasis markers only when absent from all native source text.
        # Literal operators/underscores must not disappear during ownership proof.
        for marker in ignored:
            text = text.replace(marker, "")
    return re.sub(r"\s+", " ", text).strip()


def reorder_numbered_columns(page, markdown: str) -> tuple[str, str | None]:
    """Return corrected Markdown, or an explanation when the proof fails.

    Only horizontal native text with parallel numbered regions is attempted.
    Other layouts remain untouched; this does not certify general reading order.
    """
    if len(re.findall(r"(?m)^\s*\d+[.)]\s+", markdown)) < 2:
        return markdown, None
    if page.get_drawings() or page.get_image_info() or page.get_links() or page.first_annot or page.first_widget:
        return markdown, None
    regions = []
    for index, block in enumerate(page.get_text("dict").get("blocks", [])):
        if block.get("type") != 0:
            return markdown, None
        lines = block.get("lines", [])
        text = "\n".join("".join(span["text"] for span in line.get("spans", [])) for line in lines)
        if not text.strip():
            continue
        x0, y0, x1, y1 = block["bbox"]
        rotated = any(abs(line.get("dir", (1, 0))[0] - 1) > .001 or
                      abs(line.get("dir", (1, 0))[1]) > .001 for line in lines)
        regions.append(_TextRegion(index, text, x0, y0, x1-x0, y1-y0, float(rotated)))
    numbered = [r for r in regions if re.match(r"^\s*\d+[.)]\s+", r.text)]
    parallel = any(a.left+a.width <= b.left and
                   min(a.top+a.height, b.top+b.height) > max(a.top, b.top)
                   for a in numbered for b in numbered)
    if not parallel:
        return markdown, None
    ordered, reason = order_shapes(regions)
    if reason:
        return markdown, reason
    if any(marker in markdown for marker in ("```", "~~~", "<!--", "|", "$")):
        return markdown, "Structured Markdown prevents unambiguous paragraph ownership"
    parts = re.split(r"(\n[ \t]*\n+)", markdown)
    slots = [i for i in range(0, len(parts), 2) if parts[i].strip()]
    native_text = "".join(region.text for region in regions)
    ignored = "".join(marker for marker in "*_" if marker not in native_text)
    source_keys = [_paragraph_key(region.text) for region in regions]
    markdown_keys = [_paragraph_key(parts[i], markdown=True, ignored=ignored) for i in slots]
    if (len(set(source_keys)) != len(source_keys) or len(set(markdown_keys)) != len(markdown_keys)
            or sorted(source_keys) != sorted(markdown_keys)):
        return markdown, "Native text and Markdown paragraphs do not map uniquely"
    chunks = dict(zip(markdown_keys, (parts[i] for i in slots)))
    for slot, region in zip(slots, ordered, strict=True):
        parts[slot] = chunks[_paragraph_key(region.text)]
    return "".join(parts), None
