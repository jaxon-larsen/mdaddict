"""Conservative baseline ordering inside already discovered native PDF cells.

Glyph ink boxes vary across fonts (notably decimal points and comparison signs).
Use source origins for line membership, without changing cell geometry or global
MuPDF flags. This does not discover tables or infer missing rows/columns.
"""
from collections import Counter
from bisect import bisect_right
import math
from statistics import median
import unicodedata

from .pdf_tables import AmbiguousTable


def _visible(text):
    return Counter(c for c in text if not c.isspace())


def _source_spacing(text, boundaries):
    """Apply only source-proven boundaries, retaining existing formatting there."""
    output, whitespace, offset = [], "", 0
    for char in text:
        if char.isspace():
            whitespace += char
            continue
        required = boundaries.get(offset)
        if required is True:
            whitespace = whitespace or " "
        elif required is False:
            whitespace = ""
        output.extend((whitespace, char))
        whitespace = ""
        offset += 1
    return "".join(output) + whitespace


def _cell_text(chars):
    if not chars:
        return "", False, [], {}
    lines = []
    for char in sorted(chars, key=lambda c: (c["origin"][1], c["origin"][0])):
        y = char["origin"][1]
        tolerance = max(.02, char["size"] * .02)
        if not lines or y - lines[-1][0]["origin"][1] > tolerance:
            lines.append([])
        lines[-1].append(char)
    # Nearby distinct baselines can be exponents, stacked math, or annotations.
    # Keep the native output and hold it rather than flattening their meaning.
    for before, after in zip(lines, lines[1:]):
        if after[0]["origin"][1] - before[0]["origin"][1] < .65 * max(c["size"] for c in before + after):
            raise AmbiguousTable("cell has raised or tightly stacked text")
    output, row_gaps, boundaries, offset = [], [], {}, 0
    for line in lines:
        ordered = sorted(line, key=lambda c: c["origin"][0])
        width = median(c["bbox"][2] - c["bbox"][0] for c in ordered)
        text, gaps = "", []
        for i, char in enumerate(ordered):
            if i:
                previous = ordered[i - 1]
                gap = char["bbox"][0] - previous["bbox"][2]
                if gap < -.15 * min(previous["size"], char["size"]):
                    raise AmbiguousTable("cell has overlapping glyphs")
                required = None
                if char["previous"] == previous["ordinal"]:
                    if char["separated"]:
                        required = True
                    elif gap <= .35 * width:
                        required = False
                    if required is not None:
                        boundaries[offset] = required
                if required is True or (required is None and gap > .35 * width):
                    text += " "
                # Wide aligned whitespace is evidence of unresolved columns,
                # never a proposed separator. Wrapped prose remains one cell.
                if gap > 2 * max(previous["size"], char["size"]):
                    gaps.append((previous["bbox"][2], char["bbox"][0]))
            text += char["c"]
            offset += len("".join(char["c"].split()))
        output.append(text)
        row_gaps.append(gaps)
    # Compare consecutive text lines with a linear interval scan. Do not search
    # arbitrary distant rows or impose quadratic work on long wrapped cells.
    packed = False
    for before, after in zip(row_gaps, row_gaps[1:]):
        i = j = 0
        while i < len(before) and j < len(after):
            a, b = before[i]
            c, d = after[j]
            if max(a, c) < min(b, d):
                packed = True
                break
            if b <= d:
                i += 1
            else:
                j += 1
    return "\n".join(output), packed, [(line[0]["origin"][1], min(c["size"] for c in line)) for line in lines], boundaries


def native_cell_rows(table, rows, raw):
    """Return source-owned text and an unresolved-internal-layout indicator.

    All native visible characters must survive; empty cells and covered cells
    stay distinct. Rotation, RTL, glyph overlap, boundary crossings and raised
    text fail closed. Thresholds scale with source font size, not a named PDF.
    """
    cells = [(r, c, rect) for r, row in enumerate(table.rows) for c, rect in enumerate(row.cells) if rect is not None]
    xs = sorted({v for _, _, rect in cells for v in (rect[0], rect[2])})
    ys = sorted({v for _, _, rect in cells for v in (rect[1], rect[3])})
    x_slots, y_slots = {v: i for i, v in enumerate(xs)}, {v: i for i, v in enumerate(ys)}
    slots = {}
    for r, c, rect in cells:
        for y in range(y_slots[rect[1]], y_slots[rect[3]]):
            for x in range(x_slots[rect[0]], x_slots[rect[2]]):
                if (y, x) in slots:
                    raise AmbiguousTable("source glyph ownership grid overlaps")
                slots[y, x] = (r, c, rect)
    owned = {(r, c): [] for r, c, _ in cells}
    count, ordinal = 0, 0
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            previous, separated = None, False
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    ordinal += 1
                    if not char["c"].strip():
                        separated = True
                        continue
                    predecessor, was_separated = previous, separated
                    previous, separated = ordinal, False
                    x, y = char["origin"]
                    left, top, right, bottom = table.bbox
                    if not (left <= x < right and top <= y < bottom):
                        continue
                    count += 1
                    if count > 1_000_000:
                        raise AmbiguousTable("cell text exceeds the native glyph budget")
                    size = span["size"]
                    if (line.get("dir") != (1.0, 0.0) or not math.isfinite(size) or size <= 0
                            or any(not math.isfinite(v) for v in (*char["origin"], *char["bbox"]))
                            or any(unicodedata.bidirectional(c) in {"R", "AL", "AN"} or unicodedata.combining(c) for c in char["c"])):
                        raise AmbiguousTable("cell text orientation or glyph geometry is unsupported")
                    owner = slots.get((bisect_right(ys, y) - 1, bisect_right(xs, x) - 1))
                    if owner is None:
                        raise AmbiguousTable("source glyph lacks a unique cell owner")
                    r, c, rect = owner
                    if char["bbox"][0] < rect[0] - .02 or char["bbox"][2] > rect[2] + .02:
                        raise AmbiguousTable("source glyph crosses a cell boundary")
                    if min(abs(y - rect[1]), abs(y - rect[3])) <= .02:
                        raise AmbiguousTable("source baseline lies on a cell boundary")
                    owned[r, c].append({**char, "size": size, "ordinal": ordinal,
                                       "previous": predecessor, "separated": was_separated})
    result, packed, previous_lines = [list(row) for row in rows], False, {}
    for (r, c), chars in owned.items():
        text, unresolved, baselines, boundaries = _cell_text(chars)
        packed |= unresolved
        if len(baselines) > 1:
            before = previous_lines.get(r, [])
            if len(before) == len(baselines) and all(abs(y - v) <= .02 * min(size, other_size)
                    for (y, size), (v, other_size) in zip(before, baselines)):
                # Parallel lists in multiple cells may be under-segmented rows
                # or intentionally multiline cells. Geometry alone cannot decide.
                packed = True
            previous_lines[r] = baselines
        # Non-whitespace equality does not establish lexical equivalence.
        # Encoded source spaces restore missing boundaries. Only contiguous,
        # spatially adjacent source glyphs can remove a spurious native gap.
        # Unproven gaps and formatting at existing boundaries stay untouched.
        if "".join(text.split()) != "".join((rows[r][c] or "").split()):
            result[r][c] = text
        elif rows[r][c] is not None:
            result[r][c] = _source_spacing(rows[r][c], boundaries)
    old = _visible("".join(value or "" for row in rows for value in row))
    new = _visible("".join(value or "" for row in result for value in row))
    if old - new:
        raise AmbiguousTable("baseline ordering cannot account for all native cell text")
    return result, packed
