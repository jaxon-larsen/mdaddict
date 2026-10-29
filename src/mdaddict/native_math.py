"""Bounded native display-math recovery with explicit glyph ownership.

Only flat fractions, evidenced scripts, bounded operators, and paired delimiters
are supported. Unsupported relationships keep their native text and a hold.
"""
from __future__ import annotations

from collections import Counter
import re

from mdaddict.geometry_mapping import apply_owned_expressions


class AmbiguousMath(ValueError):
    pass


def box(chars):
    return (min(c["bbox"][0] for c in chars), min(c["bbox"][1] for c in chars),
            max(c["bbox"][2] for c in chars), max(c["bbox"][3] for c in chars))


def atom(chars, text, axis, **extra):
    return {"chars": chars, "text": text, "axis": axis, "bbox": box(chars), **extra}


def script(value):
    return value if len(value) == 1 else "{" + value + "}"


SYMBOLS = {"−": "-", "–": "-", "≡": r"\equiv ", "≥": r"\ge ", "≤": r"\le ",
           "×": r"\times ", "·": r"\cdot ", "⟩": r"\rangle ", "⟨": r"\langle ",
           "σ": r"\sigma ", "λ": r"\lambda ", "ψ": r"\psi ", "∗": "*", "∈": r"\in "}


def glyph(c):
    text = c["c"]
    if "\ufffd" in text or (c.get("display") == "\ufffd" and not c.get("proven")) or any(ord(v) < 32 for v in text):
        raise AmbiguousMath("unmapped native glyph")
    if len(text) > 1 and not c.get("proven"):
        raise AmbiguousMath("operator lacks font evidence")
    if text == "P" and "MSBM" in c.get("font", "").upper():
        return r"\mathbb{P}"
    return SYMBOLS.get(text, text)


def render_row(chars, axis, size, atoms=()):
    """Render one baseline; scripts must be smaller and touch a unique base."""
    used = {id(c) for a in atoms for c in a["chars"]}
    if any(re.search(r"mono|courier|consolas", c.get("font", ""), re.I) for c in chars):
        raise AmbiguousMath("monospaced content requires code preservation")
    body, small = [], []
    for c in chars:
        if id(c) in used or not c["c"].strip():
            continue
        if c["size"] < size * .85:
            small.append(c)
        elif abs(c["origin"][1] - axis) <= 1:
            body.append(atom([c], glyph(c), axis))
        elif c["c"] in "()[]" and "CMEX" in c.get("font", "").upper() and c.get("proven"):
            body.append(atom([c], glyph(c), axis))
        else:
            raise AmbiguousMath("unsupported raised or lowered body glyph")
    body.extend(atoms)
    body.sort(key=lambda a: a["bbox"][0])
    scripts = {}
    small_groups = []
    for c in sorted(small, key=lambda c: (round(c["origin"][1], 1), c["bbox"][0])):
        group = next((g for g in small_groups if abs(g[0]["origin"][1] - c["origin"][1]) < .8
                      and -.5 <= c["bbox"][0] - g[-1]["bbox"][2] <= size * .5), None)
        if group is None:
            small_groups.append([c])
        else:
            group.append(c)
    for group in small_groups:
        c = group[0]
        bases = [a for a in body if len(a["chars"]) == 1 and
                 (a["chars"][0]["c"].isalpha() or a["chars"][0]["c"] in ")]") and
                 -.5 <= c["bbox"][0] - a["bbox"][2] <= size * .65]
        if not bases:
            raise AmbiguousMath("script has no unique adjacent base")
        base = min(bases, key=lambda a: abs(c["bbox"][0] - a["bbox"][2]))
        dy = c["origin"][1] - axis
        if abs(dy) < size * .08 or abs(dy) > size:
            raise AmbiguousMath("script baseline ambiguous")
        key = (id(base), "_" if dy > 0 else "^")
        scripts.setdefault(key, []).extend(group)
    pieces = []
    for a in body:
        text = a["text"]
        for sign in ("_", "^"):
            group = scripts.get((id(a), sign), [])
            if group:
                if max(c["origin"][1] for c in group) - min(c["origin"][1] for c in group) > .8:
                    raise AmbiguousMath("multiple script levels")
                text = text.rstrip() + sign + script("".join(glyph(c) for c in sorted(group, key=lambda c: c["bbox"][0])))
        pieces.append(text)
    # Roman prose must not be promoted to an equation merely by proximity.
    roman = "".join(c["c"] if c["size"] >= size * .85
                    and not re.search(r"CMMI|CMSY|CMEX|MSBM|MSAM", c.get("font", ""))
                    and c["c"].isalpha() else " " for c in chars)
    if any(not word.isupper() and word not in {"log", "ln", "sin", "cos", "tan", "exp"}
           for word in re.findall(r"[A-Za-z]{2,}", roman)):
        raise AmbiguousMath("prose adjacent to display math")
    result = "".join(pieces)
    result = re.sub(r"(?<![A-Za-z\\])(log|ln|sin|cos|tan|exp)(?=\()", r"\\\1 ", result)
    result = result.replace("...", r"\dots ")
    return result


def operator_atoms(chars, axis, size):
    result = []
    for op in chars:
        name = op["c"].strip()
        if name not in {r"\int", r"\sum", r"\prod"} or not op.get("proven"):
            continue
        if not 0 < axis - op["origin"][1] < size * 1.9:
            continue
        nearby = [c for c in chars if c["size"] < size * .85 and c["c"].strip()
                  and op["bbox"][0] - 1 <= c["bbox"][0] < op["bbox"][0] + size * 2.5]
        upper = [c for c in nearby if axis - size * 1.5 < c["origin"][1] < axis - size * .45]
        lower = [c for c in nearby if axis + size * .45 < c["origin"][1] < axis + size * 1.5]
        if not lower or (name == r"\int" and not upper):
            continue
        value = name
        for sign, group in (("_", lower), ("^", upper)):
            if group:
                if max(c["origin"][1] for c in group) - min(c["origin"][1] for c in group) > .8:
                    raise AmbiguousMath("operator has competing bounds")
                value += sign + script("".join(glyph(c) for c in sorted(group, key=lambda c: c["bbox"][0])))
        result.append(atom([op] + lower + upper, value + " ", axis))
    return result


def binomial_atoms(chars, fractions):
    result = []
    for left in chars:
        if left["c"] != "(" or not left.get("proven") or "CMEX" not in left.get("font", ""):
            continue
        if left["bbox"][3] - left["bbox"][1] < left["size"] * 1.8:
            continue
        rights = [c for c in chars if c["c"] == ")" and c.get("proven") and
                  c["bbox"][0] > left["bbox"][0] and abs(c["origin"][1] - left["origin"][1]) < .8]
        if not rights:
            continue
        right = min(rights, key=lambda c: c["bbox"][0])
        inner = [c for c in chars if c["c"].strip() and left["bbox"][2] - .5 <= c["bbox"][0]
                 and c["bbox"][2] <= right["bbox"][0] + .5
                 and left["origin"][1] < c["origin"][1] < left["bbox"][3] + 1]
        rows = []
        for c in sorted(inner, key=lambda c: (c["origin"][1], c["bbox"][0])):
            if not rows or abs(c["origin"][1] - rows[-1][0]["origin"][1]) > 1:
                rows.append([])
            rows[-1].append(c)
        if len(rows) != 2:
            continue
        top, bottom = ("".join(c["c"] for c in row) for row in rows)
        if not re.fullmatch(r"[A-Za-z]|\d+", top) or not re.fullmatch(r"[A-Za-z]|\d+", bottom):
            continue
        axis = (rows[0][0]["origin"][1] + rows[1][0]["origin"][1]) / 2
        expected_den = bottom + "!(" + top + "-" + bottom + ")!"
        if top.isdigit() and bottom.isdigit() and int(top) >= int(bottom):
            expected_den = bottom + "!" + str(int(top) - int(bottom)) + "!"
        formula = r"\frac{" + top + "!}{" + expected_den + "}"
        if not any(f["text"] == formula and abs(f["axis"] + f["size"] * .25 - axis) < 2
                   and 0 < f["bbox"][0] - right["bbox"][2] < left["size"] * 4 for f in fractions):
            continue  # A two-row vector is not sufficient evidence of a binomial.
        result.append(atom([left, right] + inner, r"\binom{" + top + "}{" + bottom + "}", axis))
    return result


def vector_atoms(chars):
    result = []
    for left in chars:
        if left["c"] not in {"⎡", "["}:
            continue
        if left["c"] == "[" and ("CMEX" not in left.get("font", "") or not left.get("proven")):
            continue
        end = "⎤" if left["c"] == "⎡" else "]"
        rights = [c for c in chars if c["c"] == end and c["bbox"][0] > left["bbox"][0]
                  and abs(c["origin"][1] - left["origin"][1]) < 1]
        if not rights:
            continue
        right = min(rights, key=lambda c: c["bbox"][0])
        if left["c"] == "⎡":
            bottoms = [c for c in chars if c["c"] == "⎣" and abs(c["bbox"][0] - left["bbox"][0]) < 1
                       and 0 < c["origin"][1] - left["origin"][1] < 80]
            if not bottoms:
                continue
            y1 = min(c["origin"][1] for c in bottoms) + left["size"] * 2
        else:
            y1 = left["origin"][1] + left["size"] * 2
        selected = [c for c in chars if left["bbox"][0] - .1 <= c["bbox"][0]
                    and c["bbox"][2] <= right["bbox"][2] + .1
                    and left["bbox"][1] - .1 <= c["origin"][1] <= y1]
        inner = [c for c in selected if c["c"] not in "[]⎡⎢⎣⎤⎥⎦"]
        dots = [c for c in inner if c["c"] == "."]
        if len(dots) != 3:
            continue
        ordinary = [c for c in inner if c["c"] != "."]
        if not ordinary:
            continue
        size = max(c["size"] for c in ordinary)
        if left["c"] == "[":
            if max(c["origin"][1] for c in dots) - min(c["origin"][1] for c in dots) > 1:
                continue
            axis = dots[0]["origin"][1]
            before = [c for c in ordinary if c["bbox"][0] < dots[0]["bbox"][0]]
            after = [c for c in ordinary if c["bbox"][0] > dots[-1]["bbox"][0]]
            if len(before) + len(after) != len(ordinary) or not before or not after:
                continue
            value = render_row(before, axis, size) + r" & \dots & " + render_row(after, axis, size)
        else:
            if max(c["bbox"][0] for c in dots) - min(c["bbox"][0] for c in dots) > .5:
                continue
            axes = sorted({round(c["origin"][1], 1) for c in ordinary if c["size"] > size * .85})
            if len(axes) != 2:
                continue
            groups = [[c for c in ordinary if abs(c["origin"][1] - y) < size * .8] for y in axes]
            if sum(map(len, groups)) != len(ordinary):
                continue
            value = render_row(groups[0], axes[0], size) + r" \\ \vdots \\ " + render_row(groups[1], axes[1], size)
            axis = sum(axes) / 2
        result.append(atom(selected, r"\begin{bmatrix}" + value + r"\end{bmatrix}", axis))
    return result


def split_display_row(lines, body, atoms, axis, size):
    """Large horizontal gaps separate equations, captions, and margin labels."""
    body_ids = {id(c) for c in body}
    labels = [l for l in lines if re.fullmatch(r"\(\d+(?:\.\d+)*\)", l["text"].strip())
              and all(id(c) in body_ids for c in l["chars"] if c["c"].strip())]
    label_ids = {id(c) for l in labels for c in l["chars"]}
    units = list(atoms) + [{"chars": [c], "bbox": c["bbox"], "literal": True} for c in body if id(c) not in label_ids]
    parts = []
    for unit in sorted(units, key=lambda a: a["bbox"][0]):
        if not parts or unit["bbox"][0] - max(a["bbox"][2] for a in parts[-1]) > size * 2.5:
            parts.append([])
        parts[-1].append(unit)
    results = []
    for part in parts:
        structures = [a for a in part if not a.get("literal")]
        literals = [c for a in part if a.get("literal") for c in a["chars"]]
        if not structures:
            if any(c["c"] in {"=", "≡"} for c in literals):
                raise AmbiguousMath("disconnected expression")
            continue
        selected = literals + [c for a in structures for c in a["chars"]]
        if len(selected) != len({id(c) for c in selected}):
            raise AmbiguousMath("competing geometry ownership")
        rendering = list(selected)
        punctuation = ""
        for c in sorted(literals, key=lambda c: c["bbox"][0], reverse=True):
            if c["c"] in {".", ",", ";", "■"}:
                punctuation = c["c"] + punctuation
                rendering.remove(c)
            else:
                break
        value = render_row(rendering, axis, size, structures)
        if value and len(selected) <= 250:
            results.append(atom(selected, "$" + value + "$" + punctuation, axis))
    for label in labels:
        candidates = [e for e in results if e["bbox"][2] < label["bbox"][0]]
        if candidates:
            previous = max(candidates, key=lambda e: e["bbox"][2])
            previous["chars"].extend(c for c in label["chars"] if c["c"].strip())
            previous["text"] += " " + label["text"]
    return results


def display_expressions(lines, bars):
    from mdaddict.fidelity_geometry import _fraction_atoms
    chars = [c for l in lines for c in l["chars"] if c["c"].strip()]
    fractions, _pending, _all = _fraction_atoms(lines, bars)
    base_atoms = [atom(f["chars"], f["text"], f["axis"] + f["size"] * .25) for f in fractions]
    base_atoms += binomial_atoms(chars, fractions)
    try:
        base_atoms += vector_atoms(chars)
    except AmbiguousMath:
        # A malformed script in a vector cannot abort extraction of the page.
        pass
    global_owned = {id(c) for a in base_atoms for c in a["chars"]}
    equalities = []
    for c in chars:
        if c["c"] in {"=", "≡"} and id(c) not in global_owned:
            if not any(abs(c["origin"][1] - y) < 1 for y, _s in equalities):
                equalities.append((c["origin"][1], c["size"]))
    for a in base_atoms:
        if not any(abs(a["axis"] - y) < 2 for y, _s in equalities):
            equalities.append((a["axis"], max(c["size"] for c in a["chars"])))
    expressions, pending = [], []
    for axis, size in equalities:
        try:
            ops = operator_atoms(chars, axis, size)
            atoms = [a for a in base_atoms if abs(a["axis"] - axis) < 2] + ops
            if not atoms:
                continue
            owned = {id(c) for a in atoms for c in a["chars"]}
            body = [c for c in chars if id(c) not in global_owned and id(c) not in owned and
                    ((c["size"] >= size * .85 and abs(c["origin"][1] - axis) <= 1) or
                     (c["size"] < size * .85 and abs(c["origin"][1] - axis) < size * .8) or
                     (c["c"] in "()[]" and "CMEX" in c.get("font", "") and c.get("proven")
                      and 0 < axis - c["origin"][1] < size * 1.8))]
            unsupported = [c for c in chars if id(c) not in global_owned and id(c) not in owned
                           and ((c["c"].startswith("\\") and 0 < axis - c["origin"][1] < size * 1.9)
                                or (c["c"] in "⎡⎢⎣⎤⎥⎦" and abs(axis - c["origin"][1]) < size * 3))]
            # A displaced small glyph near this display is unresolved evidence,
            # even if it fell outside a vector's delimiter rectangle.
            previous = max([y for y, _s in equalities if y < axis - 2], default=axis - size * 6)
            following = min([y for y, _s in equalities if y > axis + 2], default=axis + size * 6)
            row_ids = {id(c) for c in body}
            x0 = min(a["bbox"][0] for a in atoms + [{"bbox": c["bbox"]} for c in body])
            x1 = max(a["bbox"][2] for a in atoms + [{"bbox": c["bbox"]} for c in body])
            y0 = min(a["bbox"][1] for a in atoms + [{"bbox": c["bbox"]} for c in body])
            y1 = max(a["bbox"][3] for a in atoms + [{"bbox": c["bbox"]} for c in body])
            unsupported += [c for c in chars if c["size"] < size * .85 and id(c) not in global_owned
                            and id(c) not in owned and id(c) not in row_ids and x0 - size < c["bbox"][0] < x1 + size
                            and max((axis + previous) / 2, y0) < c["origin"][1]
                            < min((axis + following) / 2, y1)]
            if unsupported:
                raise AmbiguousMath("unsupported adjacent operator")
            expressions.extend(split_display_row(lines, body, atoms, axis, size))
        except AmbiguousMath as exc:
            # The legacy conservative recognizers may still recover a flat part,
            # but this complete display must remain explicitly unresolved.
            near = [c for c in chars if abs(c["origin"][1] - axis) < size * 1.8]
            if near:
                pending.append(("math", box(near), "complete native expression is ambiguous: " + str(exc), {}))
    return expressions, pending


def recover_display_math(lines, bars, markdown):
    expressions, pending = display_expressions(lines, bars)
    markdown, applied = apply_owned_expressions(markdown, expressions, lines)
    for e in expressions:
        if not any(e is a for a in applied):
            pending.append(("math", e["bbox"], "complete expression source mapping unavailable", {}))
    return markdown, pending, applied


def glyph_key(c):
    return (c["font"], round(c["origin"][0], 3), round(c["origin"][1], 3), c.get("native", c["c"]))


def same_glyphs(before, after):
    """PDF stream rewriting can round coordinates; text and multiplicity cannot change."""
    def groups(chars):
        result = {}
        for c in chars:
            result.setdefault((c["font"], c.get("native", c["c"])), []).append(
                (c["origin"][0], c["origin"][1], c["size"]))
        return {key: sorted(values, key=lambda v: (v[1], v[0])) for key, values in result.items()}
    a, b = groups(before), groups(after)
    return a.keys() == b.keys() and all(len(a[key]) == len(b[key]) and
        all(abs(x - y) <= .02 for va, vb in zip(a[key], b[key]) for x, y in zip(va, vb)) for key in a)


class MathPage:
    """A disposable native page whose proven equations have unique placeholders."""
    def __init__(self, doc, expressions, markers):
        self.doc = doc
        self.page = doc[0]
        self.expressions = expressions
        self.markers = markers

    def restore(self, markdown):
        from mdaddict.fidelity_geometry import _unique_span
        patches = []
        for marker, e in zip(self.markers, self.expressions):
            span = _unique_span(markdown, marker)
            if span is None:
                raise AmbiguousMath("equation placeholder was omitted or duplicated")
            patches.append((*span, e["text"]))
        for start, end, value in sorted(patches, reverse=True):
            markdown = markdown[:start] + value + markdown[end:]
        return markdown


def prepare_math_page(page):
    """Remove only owned native glyphs on a copy, verifying all others survive.

    Tiny redaction rectangles need not cover glyph ink: MuPDF removes the whole
    intersecting character. Find an exclusive point, then verify the complete
    remaining text layer before adding placeholders. Graphics/images stay intact.
    """
    import pymupdf
    from mdaddict.fidelity_geometry import _lines, _fraction_segments
    lines = _lines(page)
    bars = _fraction_segments(page.get_drawings(), page.get_text("rawdict"), tuple(page.rect))
    expressions, _pending = display_expressions(lines, bars)
    if not expressions:
        return None
    chars = [c for l in lines for c in l["chars"] if c["c"].strip()]
    counts = Counter(id(c) for e in expressions for c in e["chars"])
    expressions = [e for e in expressions if all(counts[id(c)] == 1 for c in e["chars"])]
    owned = {id(c) for e in expressions for c in e["chars"]}
    remaining = [c for c in chars if id(c) not in owned]
    rectangles = []
    for c in chars:
        if id(c) not in owned:
            continue
        x0, y0, x1, y1 = c["bbox"]
        overlaps = [v["bbox"] for v in remaining if v["bbox"][0] < x1 and v["bbox"][2] > x0
                    and v["bbox"][1] < y1 and v["bbox"][3] > y0]
        xs = sorted({x0, x1} | {max(x0, min(x1, b[i])) for b in overlaps for i in (0, 2)})
        ys = sorted({y0, y1} | {max(y0, min(y1, b[i])) for b in overlaps for i in (1, 3)})
        rect = None
        area = 0
        for left, right in zip(xs, xs[1:]):
            for top, bottom in zip(ys, ys[1:]):
                x, y = (left + right) / 2, (top + bottom) / 2
                candidate_area = (right - left) * (bottom - top)
                if candidate_area > area and right - left > .02 and bottom - top > .02 and not any(
                        b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in overlaps):
                    rect = pymupdf.Rect(left + .002, top + .002, right - .002, bottom - .002)
                    area = candidate_area
        if rect is None:
            return None
        rectangles.append(rect)
    if not expressions:
        return None
    doc = pymupdf.open()
    try:
        doc.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
        copied = doc[0]
        for rect in rectangles:
            copied.add_redact_annot(rect, fill=False, cross_out=False)
        copied.apply_redactions(images=0, graphics=0)
        after = [c for l in _lines(copied) for c in l["chars"] if c["c"].strip()]
        if not same_glyphs(remaining, after):
            doc.close()
            return None
        markers = []
        for i, e in enumerate(expressions):
            marker = f"ZQXMATH{i:04d}ZQX"
            if marker in page.get_text():
                doc.close()
                return None
            fontsize = min(10, (e["bbox"][2] - e["bbox"][0]) / pymupdf.get_text_length(marker, fontsize=1))
            if fontsize <= 3:
                doc.close()
                return None
            copied.insert_text((e["bbox"][0], e["axis"]), marker, fontsize=fontsize)
            markers.append(marker)
        return MathPage(doc, expressions, markers)
    except Exception:
        doc.close()
        raise
