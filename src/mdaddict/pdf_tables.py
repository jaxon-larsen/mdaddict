"""Serialize native ruled-table cells without inferring missing relationships.

PyMuPDF supplies the rectangles and extracted text. This adapter only accepts a
complete rectangular tiling; borderless discovery and uncertain spans stay with
the existing reader/review path. No additional parser or dependency is loaded.
"""
from html import escape
import math

from .strategy import table_markdown


class AmbiguousTable(ValueError):
    """Native geometry cannot account for every output grid position."""


def native_table_markdown(table, rows):
    geometry = [row.cells for row in table.rows]
    height, width = len(rows), len(rows[0]) if rows else 0
    if not height or not width or len(geometry) != height or any(
            len(values) != width for values in [*rows, *geometry]):
        raise AmbiguousTable("inconsistent row/column geometry")
    rectangles = [cell for row in geometry for cell in row if cell is not None]
    if any(len(rect) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v) for v in rect) or rect[0] >= rect[2] or rect[1] >= rect[3]
            for rect in [table.bbox, *rectangles]):
        raise AmbiguousTable("invalid cell bounds")
    # Use the reader's exact shared edges. Near or conflicting boundaries are
    # rejected rather than rounded into an invented row/column relationship.
    xs = sorted({v for rect in [table.bbox, *rectangles] for v in (rect[0], rect[2])})
    ys = sorted({v for rect in [table.bbox, *rectangles] for v in (rect[1], rect[3])})
    if len(xs) != width + 1 or len(ys) != height + 1 or (
            xs[0], ys[0], xs[-1], ys[-1]) != tuple(table.bbox):
        raise AmbiguousTable("cell edges do not form the declared grid")
    x_indices, y_indices = {v: i for i, v in enumerate(xs)}, {v: i for i, v in enumerate(ys)}
    occupied, spans = set(), {}
    for r, cells in enumerate(geometry):
        for c, rect in enumerate(cells):
            if rect is None:
                if rows[r][c] not in (None, ""):
                    raise AmbiguousTable("covered position contains unowned text")
                continue
            left, top, right, bottom = rect
            r1, c1 = y_indices[top], x_indices[left]
            r2, c2 = y_indices[bottom], x_indices[right]
            if (r1, c1) != (r, c):
                raise AmbiguousTable("cell origin disagrees with its grid position")
            positions = {(rr, cc) for rr in range(r1, r2) for cc in range(c1, c2)}
            if positions & occupied:
                raise AmbiguousTable("overlapping cells")
            occupied.update(positions)
            spans[r, c] = (r2 - r1, c2 - c1)
    if len(occupied) != height * width:
        raise AmbiguousTable("grid has positions without a cell owner")
    if all(span == (1, 1) for span in spans.values()):
        values = [["" if value is None else value for value in row] for row in rows]
        if table.header.external:
            values.insert(0, table.header.names)
        return table_markdown(values)
    if table.header.external:
        raise AmbiguousTable("external header relationships are not mapped")
    output = ["<table>"]
    for r, values in enumerate(rows):
        cells = []
        for c, value in enumerate(values):
            if (r, c) not in spans:
                continue
            rowspan, colspan = spans[r, c]
            attrs = (f' rowspan="{rowspan}"' if rowspan > 1 else "") + (
                f' colspan="{colspan}"' if colspan > 1 else "")
            text = escape(str(value) if value is not None else "", quote=False)
            text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
            tag = "th" if r == 0 else "td"
            cells.append(f"<{tag}{attrs}>{text}</{tag}>")
        output.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join([*output, "</table>"])
