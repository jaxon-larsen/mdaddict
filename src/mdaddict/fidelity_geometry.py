"""Conservative, network-free recovery and unresolved-region discovery.

Geometry establishes a small set of layout facts, never algebraic equivalence.
Unsupported layouts are retained for review instead of guessed. Offsets always
address the returned Markdown, after any deterministic replacements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re


GEOMETRY_REVISION = "geometry-2"


@dataclass
class Region:
    id: str
    kind: str
    bbox: tuple[float, float, float, float]
    start: int
    end: int
    text: str
    high_risk: bool = True
    reason: str = ""
    constraints: dict = field(default_factory=dict)


@dataclass
class PageAnalysis:
    markdown: str
    regions: list[Region]
    resolved: int = 0


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _touch(a, b, padding=2):
    return not (a[2] + padding < b[0] or b[2] + padding < a[0]
                or a[3] + padding < b[1] or b[3] + padding < a[1])


def _inside(a, b):
    return a[0] >= b[0] - 1 and a[1] >= b[1] - 1 and a[2] <= b[2] + 1 and a[3] <= b[3] + 1


def _unique_span(text, source):
    """Allow extraction whitespace and markdown formatting differences, never approximate word matches."""
    ligatures = {"\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff", "\ufb03": "ffi", "\ufb04": "ffl"}
    source_clean = "".join(ligatures.get(c, c) for c in source)
    text_clean = "".join(ligatures.get(c, c) for c in text)
    # Match normalized spelling, but every caller slices the original Markdown.
    offsets = [i for i, c in enumerate(text) for _ in ligatures.get(c, c)]
    has_brackets = "[" in source_clean or "]" in source_clean
    ignored = "*_" if has_brackets else "*_[]"
    chars = [re.escape(c) for c in source_clean if not c.isspace() and c not in ignored]
    if not chars:
        return None
    lead = r"[*_]*" if has_brackets else r"[*_\[\]]*"
    pattern = (r"[*_]*\s*[*_]*" if has_brackets else r"[*_\[\]]*\s*[*_\[\]]*").join(chars)
    matches = [m for m in re.finditer(lead + pattern + lead, text_clean)
               if (m.start() == 0 or offsets[m.start() - 1] != offsets[m.start()])
               and (m.end() == len(offsets) or offsets[m.end() - 1] != offsets[m.end()])]
    if len(matches) != 1:
        return None
    match = matches[0]
    return offsets[match.start()], offsets[match.end() - 1] + 1


def _baseline_superscript_labels(page):
    """Superscript-flagged span texts that sit on the surrounding baseline.

    The pinned Markdown adapter wraps every superscript-flagged span in brackets.
    Computer Modern formulas often set that flag on ordinary glyphs. A glyph is
    treated as raised only when its bottom is clearly above a body-text neighbor.
    """
    getter = getattr(page, "get_text", None)
    if getter is None:
        return set()
    try:
        raw = getter("dict")
    except Exception:
        return set()
    if not isinstance(raw, dict):
        return set()
    false, genuine = {}, set()
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [span for span in line.get("spans", []) if span.get("text", "").strip()]
            body = [span for span in spans if not span.get("flags", 0) & 1]
            baseline = None
            if body:
                body_size = max(span["size"] for span in body)
                anchors = [span for span in body if span["size"] >= body_size - 0.6]
                baseline = max(span["bbox"][3] for span in anchors)
            for span in spans:
                if not span.get("flags", 0) & 1:
                    continue
                label = span.get("text", "")
                stripped = label.strip()
                if not stripped or "\n" in label or "[" in label or "]" in label or len(stripped) > 40:
                    continue
                # A hanging subscript pulls the line bottom down. Compare with
                # the full-size body glyphs, and keep only a clear rise.
                raised = baseline is None or baseline - span["bbox"][3] > 3
                if raised:
                    genuine.add(stripped)
                else:
                    false.setdefault(stripped, set()).add(label)
    return {label for stripped, variants in false.items() if stripped not in genuine for label in variants}


def unwrap_baseline_superscripts(markdown, labels):
    for label in sorted(labels, key=len, reverse=True):
        # Pass the label through a callable so backslashes are never re-escapes.
        markdown = re.sub(r"\[" + re.escape(label) + r"\](?!\()", lambda _match, value=label: value, markdown)
    return markdown


def _font_glyph_maps(page):
    doc = getattr(page, "parent", None)
    get_fonts = getattr(page, "get_fonts", None)
    if not doc or not get_fonts:
        return {}
    glyph_to_latex = {
        "summationdisplay": r"\sum ",
        "summationtext": r"\sum ",
        "productdisplay": r"\prod ",
        "producttext": r"\prod ",
        "coproductdisplay": r"\coprod ",
        "coproducttext": r"\coprod ",
        "integraldisplay": r"\int ",
        "integraltext": r"\int ",
        "uniondisplay": r"\bigcup ",
        "uniontext": r"\bigcup ",
        "intersectiondisplay": r"\bigcap ",
        "intersectiontext": r"\bigcap ",
        "parenleftBigg": "(",
        "parenrightBigg": ")",
        "parenleftbigg": "(",
        "parenrightbigg": ")",
        "parenleftBig": "(",
        "parenrightBig": ")",
        "parenleftbig": "(",
        "parenrightbig": ")",
        "bracketleftBigg": "[",
        "bracketrightBigg": "]",
        "bracketleftbigg": "[",
        "bracketrightbigg": "]",
        "bracketleftBig": "[",
        "bracketrightBig": "]",
        "bracketleftbig": "[",
        "bracketrightbig": "]",
        "braceleftBigg": "{",
        "bracerightBigg": "}",
        "braceleftbigg": "{",
        "bracerightbigg": "}",
        "braceleftBig": "{",
        "bracerightBig": "}",
        "braceleftbig": "{",
        "bracerightbig": "}",
    }
    font_maps = {}
    try:
        fonts = get_fonts()
    except Exception:
        return {}
    for f in fonts:
        xref = f[0]
        font_name = f[3]
        if not xref:
            continue
        try:
            font_obj = doc.xref_object(xref)
            m = re.search(r"/Encoding\s+(\d+)\s+0\s+R", font_obj)
            if not m:
                continue
            enc_xref = int(m.group(1))
            enc_obj = doc.xref_object(enc_xref)
            diff_m = re.search(r"/Differences\s*\[(.*?)\]", enc_obj, re.DOTALL)
            if not diff_m:
                continue
            mapping = {}
            current_code = 0
            for tok in diff_m.group(1).split():
                if tok.isdigit():
                    current_code = int(tok)
                elif tok.startswith("/"):
                    glyph = tok[1:]
                    if glyph in glyph_to_latex:
                        mapping[current_code] = glyph_to_latex[glyph]
                    current_code += 1
            if mapping:
                font_maps[font_name] = mapping
                if "+" in font_name:
                    font_maps[font_name.split("+", 1)[1]] = mapping
        except Exception:
            continue
    return font_maps


def _lines(page, raw=None):
    font_maps = _font_glyph_maps(page) if hasattr(page, "parent") else {}
    trace = {}
    if hasattr(page, "get_texttrace"):
        for span in page.get_texttrace():
            for code, _gid, origin, _box in span["chars"]:
                trace[(span["font"], round(origin[0], 3), round(origin[1], 3))] = chr(code)
    result = []
    for block in (raw if raw is not None else page.get_text("rawdict")).get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            if tuple(line.get("dir", (1, 0))) != (1, 0):
                continue  # Rotated writing is outside the supported geometry.
            chars = []
            for span in line.get("spans", []):
                font = span.get("font", "")
                font_map = font_maps.get(font) or font_maps.get(font.split("+")[-1])
                for c in span.get("chars", []):
                    char_c = c.get("c", "")
                    code = ord(char_c) if len(char_c) == 1 else 0
                    if font_map and code in font_map:
                        char_c = font_map[code]
                    display = trace.get((font, round(c["origin"][0], 3), round(c["origin"][1], 3)), c["c"])
                    chars.append({**c, "c": char_c, "native": c["c"], "display": display,
                                  "proven": char_c != c["c"] or display != "\ufffd",
                                  "size": span["size"], "font": font})
            if chars:
                result.append({"bbox": tuple(line["bbox"]), "chars": chars,
                               "text": "".join(c["c"] for c in chars)})
    return result


def _segments(drawings):
    result = []
    for drawing in drawings:
        for item in drawing.get("items", []):
            if item[0] == "l":
                a, b = item[1:3]
                if abs(a.y - b.y) <= .35 and abs(a.x - b.x) >= 2:
                    result.append((min(a.x, b.x), (a.y + b.y) / 2, max(a.x, b.x)))
    return result


def _fraction_segments(drawings, raw, page_rect=None):
    """Include thin filled rules and axis-aligned one-pixel stencil rules.

    Reject horizontal lines spanning > 45% page width or residing in top/bottom 8% margins.
    A small arbitrary raster image is not evidence of a mathematical stroke.
    PDF stencil masks with a single pixel have a uniform painted silhouette.
    """
    if page_rect is not None:
        page_y0 = page_rect[1]
        page_width = page_rect[2] - page_rect[0]
        page_height = page_rect[3] - page_rect[1]
    else:
        page_y0 = 0.0
        page_width = float(raw.get("width") or 612.0)
        page_height = float(raw.get("height") or 792.0)

    result = _segments([d for d in drawings if (d.get("stroke_opacity", 1) or 0) > 0
                        and (d.get("width", 1) or 0) <= 1])
    for drawing in drawings:
        for item in drawing.get("items", []):
            if item[0] == "re" and drawing.get("fill") is not None and (drawing.get("fill_opacity", 1) or 0) > 0:
                box = item[1]
                if 0 < box.height <= 1 and box.width >= 2:
                    result.append((box.x0, (box.y0 + box.y1) / 2, box.x1))
    for info in raw.get("blocks", []):
        if info.get("type") != 1:
            continue
        a, b, c, d, _, _ = info["transform"]
        x0, y0, x1, y1 = info["bbox"]
        if (info["width"] == info["height"] == 1 and info["colorspace"] == 0
                and info["bpc"] == 1 and not info.get("has-mask")
                and abs(b) < .01 and abs(c) < .01 and abs(a) >= 2
                and 0 < abs(d) <= 1 and 0 < y1 - y0 <= 1):
            import pymupdf
            # The decoded stencil is an alpha plane. Empty masks do not
            # establish a bar, even when their bounding boxes are identical.
            try:
                painted = pymupdf.Pixmap(info["image"]).samples == b"\xff"
            except (ValueError, RuntimeError):
                painted = False
            if painted:
                result.append((x0, (y0 + y1) / 2, x1))

    filtered = [bar for bar in result
                if not ((bar[2] - bar[0]) > 0.45 * page_width
                        or bar[1] < page_y0 + 0.08 * page_height
                        or bar[1] > page_y0 + 0.92 * page_height)]
    # Duplicate painting of a rule must not create competing fraction scopes.
    return list(dict.fromkeys(tuple(round(v, 2) for v in bar) for bar in filtered))


def _fraction_operand(chars, bars):
    """Only flat operands; a radical needs both its glyph and scoped rule."""
    chars = [c for c in chars if c["c"].strip() and c["c"] != "\x00"]
    chars = sorted(chars, key=lambda c: c["bbox"][0])
    roots = [c for c in chars if c["c"] == "√"]
    ordinary = [c for c in chars if c["c"] != "√"]
    while ordinary and ordinary[-1]["c"] in {",", ".", ";"}:
        ordinary.pop()
    chars = [c for c in chars if c in ordinary or c in roots]
    if not ordinary:
        return None
    body_ordinary = [c for c in ordinary if c["c"] not in "()[]"]
    if body_ordinary and max(c["origin"][1] for c in body_ordinary) - min(c["origin"][1] for c in body_ordinary) > .75:
        return None  # Raised/lowered and nested expressions need review.
    if any(abs(c["size"] - ordinary[0]["size"]) > .75 for c in ordinary):
        return None
    text = "".join(c["c"] for c in ordinary)
    normalized = text.replace("−", "-").replace("–", "-").replace("×", "*").replace("·", "*")
    cleaned_alpha = re.sub(r"(?i)\b(?:d[a-z]|ln|exp|sin|cos|tan|log)\b", "x", normalized)
    if (not re.fullmatch(r"[A-Za-z0-9()+\-*!/|⟩⟨\u27e8\u27e9]+", normalized)
            or re.search(r"[A-Za-z]{2,}", cleaned_alpha) or not re.search(r"[A-Za-z0-9]", normalized)):
        return None
    depth = 0
    for char in normalized:
        depth += (char == "(") - (char == ")")
        if depth < 0:
            return None
    if depth:
        return None
    if any(right["bbox"][0] - left["bbox"][2] > ordinary[0]["size"] * .6
           for left, right in zip(chars, chars[1:])):
        return None
    if any(left["c"].isdigit() and right["c"].isdigit()
           and right["bbox"][0] - left["bbox"][2] > ordinary[0]["size"] * .15
           for left, right in zip(chars, chars[1:])):
        return None  # Separate numeric tokens cannot become a different value.

    norm_kets = normalized.replace("⟩", r"\rangle").replace("⟨", r"\langle").replace("\u27e9", r"\rangle").replace("\u27e8", r"\langle")

    if not roots:
        return norm_kets
    if len(roots) != 1:
        return None
    root = roots[0]
    scoped = [(x0, y, x1) for x0, y, x1 in bars
              if abs(x0 - root["bbox"][2]) <= 1.5
              and abs(root["origin"][1] - y) < root["size"] * .75]
    if len(scoped) != 1:
        return None
    rx0, ry, rx1 = scoped[0]
    radicand = [c for c in ordinary if rx0 - 1 <= (c["bbox"][0] + c["bbox"][2]) / 2 <= rx1 + 1]
    outside = [c for c in ordinary if c not in radicand]
    if not radicand or len(radicand) + len(outside) != len(ordinary):
        return None
    left_chars = [c for c in outside if c["bbox"][2] <= root["bbox"][0] + 1]
    right_chars = [c for c in outside if c["bbox"][0] >= rx1 - 1]
    if len(left_chars) + len(right_chars) != len(outside):
        return None
    left_text = "".join(c["c"] for c in sorted(left_chars, key=lambda c: c["bbox"][0])).replace("−", "-").replace("–", "-").replace("×", "*").replace("·", "*")
    right_text = "".join(c["c"] for c in sorted(right_chars, key=lambda c: c["bbox"][0])).replace("−", "-").replace("–", "-").replace("×", "*").replace("·", "*")
    radicand_text = "".join(c["c"] for c in sorted(radicand, key=lambda c: c["bbox"][0])).replace("−", "-").replace("–", "-").replace("×", "*").replace("·", "*")
    return left_text + r"\sqrt{" + radicand_text + "}" + right_text


def _fractions_conflict(f, g):
    if any(id(c) in {id(x) for x in f["chars"]} for c in g["chars"]):
        return True
    if not _touch(f["bbox"], g["bbox"], 0):
        return False
    min_size = min(f["size"], g["size"])
    if abs(f["axis"] - g["axis"]) >= min_size * 1.8:
        if not (f["bbox"][1] <= g["axis"] <= f["bbox"][3] or g["bbox"][1] <= f["axis"] <= g["bbox"][3]):
            return False
    return True


def _fraction_atoms(lines, bars):
    """Return only geometry-proven, nonoverlapping flat fractions."""
    fractions, pending = [], []
    chars = [c for line in lines for c in line["chars"] if c["c"].strip()]
    pure_fraction_bars = [b for b in bars if not any(c["c"] == "√" and abs(b[0] - c["bbox"][2]) <= 1.5 and abs(c["origin"][1] - b[1]) < c["size"] * 0.75 for c in chars)]
    for x0, y, x1 in pure_fraction_bars:
        near = [c for c in chars if x0 - .8 <= (c["bbox"][0] + c["bbox"][2]) / 2 <= x1 + .8
                and abs(c["origin"][1] - y) < c["size"] * 1.5]
        above = [c for c in near if c["origin"][1] < y - .8]
        below = [c for c in near if c["origin"][1] > y + .8]
        if not above or not below:
            continue
        box = _union([c["bbox"] for c in near] + [(x0, y, x1, y)])
        numerator, denominator = _fraction_operand(above, bars), _fraction_operand(below, bars)
        if (len(above) + len(below) != len(near) or not numerator or not denominator
                or any(c["bbox"][0] < x0 - 1 or c["bbox"][2] > x1 + 1 for c in near)):
            pending.append(("math", box, "fraction operand or radical scope ambiguous", {}))
            continue
        fractions.append({"bbox": box, "chars": above + below, "axis": y,
                          "size": near[0]["size"], "text": r"\frac{" + numerator + "}{" + denominator + "}"})
    # Overlapping candidates (including nested bars) are never resolved by order.
    safe = [f for f in fractions if not any(_touch(f["bbox"], box, 0) for _, box, _, _ in pending)
            and not any(f is not g and _fractions_conflict(f, g) for g in fractions)]
    for f in fractions:
        if f not in safe:
            pending.append(("math", f["bbox"], "overlapping fraction scopes", {}))
    return safe, pending, fractions


def _fractions(lines, bars, markdown):
    """Recover isolated flat fraction expressions without deleting unmapped text."""
    safe, pending, fractions = _fraction_atoms(lines, bars)
    chars = [c for line in lines for c in line["chars"] if c["c"].strip()]
    groups = []
    for f in sorted(safe, key=lambda f: (f["axis"], f["bbox"][0])):
        group = next((g for g in groups if abs(g[0]["axis"] - f["axis"]) < 1), None)
        if group is None:
            groups.append([f])
        else:
            group.append(f)
    patches, copies, resolved = [], [], 0
    for group in groups:
        owned = {id(c) for f in group for c in f["chars"]}
        size, axis = group[0]["size"], group[0]["axis"]
        row = [c for c in chars if id(c) not in owned
               and abs(c["origin"][1] - (axis + size * .25)) <= 2.5]
        atoms = sorted(group + [{"bbox": c["bbox"], "chars": [c], "text": c["c"]} for c in row],
                       key=lambda a: a["bbox"][0])
        runs = []
        for atom in atoms:
            if not runs or atom["bbox"][0] - runs[-1][-1]["bbox"][2] > size * 2:
                runs.append([])
            runs[-1].append(atom)
        for run in runs:
            members = [f for f in group if any(f is a for a in run)]
            if not members:
                continue
            first_idx = min(i for i, a in enumerate(run) if any(a is f for f in members))
            last_idx = max(i for i, a in enumerate(run) if any(a is f for f in members))

            # Trim leading non-math tokens (prose words) before the first fraction
            start_idx = first_idx
            while start_idx > 0:
                prev_atom = run[start_idx - 1]
                t = prev_atom["text"]
                gap = run[start_idx]["bbox"][0] - prev_atom["bbox"][2]
                if gap > 8:
                    break
                if t in "=+-*×·≡≤≥<>|/\u2261\u25a0()[]{}":
                    start_idx -= 1
                elif re.fullmatch(r"[0-9]", t):
                    start_idx -= 1
                elif re.fullmatch(r"[A-Za-z]", t):
                    if start_idx >= 2 and re.fullmatch(r"[A-Za-z]", run[start_idx - 2]["text"]):
                        break
                    start_idx -= 1
                else:
                    break

            # Trim trailing non-math tokens (prose words) after the last fraction
            end_idx = last_idx + 1
            while end_idx < len(run):
                atom = run[end_idx]
                t = atom["text"]
                gap = atom["bbox"][0] - run[end_idx - 1]["bbox"][2]
                if gap > 8:
                    break
                if t in "=+-*×·≡≤≥<>|/\u2261\u25a0()[]{},.;!⟩⟨\u27e8\u27e9":
                    end_idx += 1
                elif re.fullmatch(r"[0-9]", t):
                    end_idx += 1
                elif re.fullmatch(r"[A-Za-z]", t):
                    if end_idx + 1 < len(run) and re.fullmatch(r"[A-Za-z]", run[end_idx + 1]["text"]):
                        break
                    end_idx += 1
                else:
                    break

            run = run[start_idx:end_idx]
            box = _union([a["bbox"] for a in run])
            selected = {id(c) for a in run for c in a["chars"]}
            run_chars = [c for a in run for c in a["chars"]]
            min_orig = min(c["origin"][1] for c in run_chars)
            max_orig = max(c["origin"][1] for c in run_chars)
            extra = [c for c in chars if id(c) not in selected and _touch(c["bbox"], box, 0)
                     and not c["c"].isspace() and min_orig - 3 <= c["origin"][1] <= max_orig + 3]
            literals = "".join(a["text"] for a in run if not any(a is f for f in members)).replace("−", "-").replace("–", "-")
            cleaned_literals = re.sub(r"(?i)\b(?:d[a-z]|ln|exp|sin|cos|tan|log)\b", "x", literals.replace(" ", ""))
            if (extra or not re.fullmatch(r"[A-Za-z0-9()+\-*!=.,|⟩⟨/\u27e8\u27e9\u2261\u25a0×·\xd7\xb7 ]*", literals)
                    or re.search(r"[A-Za-z]{3,}", cleaned_literals)):
                pending.append(("math", box, "fraction expression contains unsupported adjacent content", {}))
                continue
            tokens, punctuation = [a["text"] for a in run], ""
            while tokens and tokens[-1] in {",", ".", ";"}:
                punctuation = tokens.pop() + punctuation
            expression = " ".join(tokens).replace("⟩", r"\rangle").replace("⟨", r"\langle").replace("\u27e9", r"\rangle").replace("\u27e8", r"\langle").replace("−", "-").replace("–", "-").replace("×", r"\times ").replace("·", r"\cdot ")
            value = "$" + expression + "$" + punctuation
            source = "".join(c["c"] for c in chars if id(c) in selected)
            span = _unique_span(markdown, source)
            if span:
                start, end = span
                prefix = markdown[markdown.rfind("\n", 0, start) + 1:start]
                suffix = markdown[end:markdown.find("\n", end) if "\n" in markdown[end:] else len(markdown)]
                if ((re.search(r"[A-Za-z]{2,}", prefix) and re.search(r"[A-Za-z]{2,}", suffix))
                        or re.search(r"(?m)^\s*(\x60{3,}|~{3,})", markdown[:start])):
                    span = None
                else:
                    before = [line for line in lines if line["bbox"][3] < box[1]]
                    after = [line for line in lines if line["bbox"][1] > box[3]]
                    neighbors = [(max(before, key=lambda l: l["bbox"][3]), True)] if before else []
                    if after:
                        neighbors.append((min(after, key=lambda l: l["bbox"][1]), False))
                    for line, precedes in neighbors:
                        anchor = _unique_span(markdown, line["text"])
                        if anchor and (start < anchor[1] if precedes else end > anchor[0]):
                            span = None
                            break
            if span:
                if not any(max(span[0], p[0]) < min(span[1], p[1]) for p in patches):
                    patches.append((*span, value))
                else:
                    copies.append((box, value))
                    pending.append(("math", box, "fraction recovered separately; original Markdown mapping requires review", {}))
            else:
                copies.append((box, value))
                pending.append(("math", box, "fraction recovered separately; original Markdown mapping requires review", {}))
            resolved += len(members)
    for start, end, value in sorted(patches, reverse=True):
        markdown = markdown[:start] + value + markdown[end:]
    for box, value in copies:
        markdown += ("\n\n### Equation recovered from native geometry\n\n"
                     "<!-- bbox: " + ",".join(f"{v:.2f}" for v in box) + " -->\n\n" + value + "\n")
    return markdown, pending, resolved, [f["bbox"] for f in fractions]


def _overlines(lines, segments, markdown):
    patches, unresolved, used = [], [], set()
    recovered = 0
    for line in lines:
        chars, groups = line["chars"], []
        for segment_index, (x0, y, x1) in enumerate(segments):
            selected = [i for i, c in enumerate(chars) if c["c"].strip()
                        and x0 - .8 <= (c["bbox"][0] + c["bbox"][2]) / 2 <= x1 + .8
                        and -.8 <= c["bbox"][1] - y <= 4]
            if not selected:
                continue
            first, last = selected[0], selected[-1]
            box = _union([c["bbox"] for c in chars[first:last + 1]])
            if abs(box[0] - x0) > 2 or abs(box[2] - x1) > 2:
                continue
            used.add(segment_index)
            region_box = _union([line["bbox"], (x0, y, x1, y)])
            # A numerator above the same stroke makes this a possible fraction.
            above = any(c["c"].strip() and c["bbox"][0] < x1 and c["bbox"][2] > x0
                        and 0 <= y - c["bbox"][3] <= 12
                        for other in lines if other is not line for c in other["chars"])
            content = "".join(c["c"] for c in chars[first:last + 1])
            # Numeric bars commonly belong to fractions or radicals. Supported
            # overlines are alphabetic boolean groups; numeric scope is deferred.
            if above or not re.fullmatch(r"[A-Za-z+() \-]+", content):
                unresolved.append(("math", region_box, "ambiguous horizontal mathematical stroke", {}))
                continue
            groups.append((first, last + 1))
        if not groups:
            continue
        groups = sorted(set(groups))
        span = _unique_span(markdown, line["text"])
        overlap = any(left[1] > right[0] for left, right in zip(groups, groups[1:]))
        if span is None or overlap or any(r[0] == "math" and _touch(r[1], line["bbox"], 0) for r in unresolved):
            unresolved.append(("math", line["bbox"], "overline scope or source mapping ambiguous", {}))
            continue
        # Avoid double wrapping a native converter's existing mathematical markup.
        if "\\overline" in markdown[span[0]:span[1]] or "\\bar" in markdown[span[0]:span[1]]:
            continue
        value = line["text"]
        for first, end in reversed(groups):
            value = value[:first] + r"\overline{" + value[first:end] + "}" + value[end:]
        patches.append((span[0], span[1], "$" + value + "$"))
        recovered += len(groups)
    for start, end, value in sorted(patches, reverse=True):
        markdown = markdown[:start] + value + markdown[end:]
    return markdown, unresolved, used, recovered


def _table_boxes(get_found_tables):
    """Recognized cell grids are already reconstructed by native_tables."""
    found_tables = get_found_tables()
    if found_tables is None:
        return []
    return [tuple(t.bbox) for t in found_tables.tables]


def _ruled_tables(lines, drawings, markdown):
    """Recover simple numeric tables with a header rule and partial separators.

    PyMuPDF's closed-cell detector deliberately misses these open grids. Numeric
    body columns provide unambiguous anchors; headers must have the same number
    of whitespace-delimited labels. Spanning headers are left unresolved.
    """
    boxes, patches, pending = [], [], []
    verticals = [(min(i[1].x, i[2].x), min(i[1].y, i[2].y), max(i[1].y, i[2].y))
                 for d in drawings for i in d.get("items", [])
                 if i[0] == "l" and abs(i[1].x-i[2].x) < .4 and abs(i[1].y-i[2].y) > 5]
    for x0, y, x1 in _segments(drawings):
        if x1-x0 < 35:
            continue
        dividers = [(x, top, bottom) for x, top, bottom in verticals
                    if x0 + 2 < x < x1 - 2 and top <= y + 1 and bottom >= y - 15]
        if not dividers:
            continue
        xs = [v[0] for v in dividers]
        attached = [v for v in verticals if any(abs(v[0]-x) < .5 for x in xs)]
        bottom = max([y] + [v[2] for v in dividers])
        # Only contiguous vertical fragments belong to this table.
        while True:
            next_bottom = max([bottom] + [v[2] for v in attached if v[1] <= bottom + 2])
            if next_bottom == bottom:
                break
            bottom = next_bottom
        box = (x0 - 1, min(v[1] for v in dividers) - 1, x1 + 1, bottom + 1)
        selected = [l for l in lines if _inside(l["bbox"], box)]
        rows = []
        for line in sorted(selected, key=lambda l: (l["bbox"][1], l["bbox"][0])):
            if not rows or abs(rows[-1][0]["bbox"][1] - line["bbox"][1]) > 2:
                rows.append([])
            rows[-1].append(line)
        if len(rows) < 4:
            continue
        values = [" ".join(l["text"] for l in sorted(row, key=lambda l:l["bbox"][0])).split() for row in rows]
        body = values[1:]
        if not all(re.fullmatch(r"-?\d+(?:\.\d+)?", token) for row in body for token in row):
            continue
        columns = len(body[0])
        if columns < 2:
            continue
        boxes.append(box)
        if any(len(row) != columns for row in values):
            pending.append(("table", box, "open-grid table has ambiguous header or empty-cell alignment",
                            {"rows": len(values), "columns": columns}))
            continue
        source = "\n".join(l["text"] for l in lines if l in selected)
        span = _unique_span(markdown, source)
        if span is None:
            # Existing native Markdown may already encode the exact grid.
            expected = [[c.strip() for c in row] for row in values]
            blocks = re.findall(r"(?m)^\|[^\n]*(?:\n\|[^\n]*)+", markdown)
            parsed = [[[c.strip() for c in line.strip().strip("|").split("|")]
                       for line in block.splitlines() if not re.fullmatch(r"[| :\-]+", line)] for block in blocks]
            if expected in parsed:
                continue
            pending.append(("table", box, "open-grid table source mapping unavailable",
                            {"rows": len(values), "columns": columns}))
            continue
        grid = ["| " + " | ".join(row) + " |" for row in values]
        grid.insert(1, "| " + " | ".join(["---"] * columns) + " |")
        patches.append((*span, "\n".join(grid)))
    for start, end, value in sorted(patches, reverse=True):
        markdown = markdown[:start] + value + markdown[end:]
    return markdown, boxes, pending, len(patches)


def _matrices(lines, markdown):
    """Recognize extensible brackets around aligned numeric rows and vectors."""
    patches, pending = [], []

    # 1. Adobe Symbol extensible parentheses (\uf8eb ... \uf8f8)
    for left in [l for l in lines if l["text"] == "\uf8eb"]:
        ends = [l for l in lines if "\uf8f8" in l["text"] and l["bbox"][0] > left["bbox"][0]
                and 0 < l["bbox"][1] - left["bbox"][1] < 150]
        if not ends:
            continue
        right = min(ends, key=lambda l: l["bbox"][0])
        box = _union([left["bbox"], right["bbox"]])
        # The bottom bracket piece's bbox ends above the last row's baseline.
        box = (box[0], box[1] - 1, box[2], box[3] + 12)
        selected = [l for l in lines if _inside(l["bbox"], box)]
        rows = [l for l in selected if re.fullmatch(r"-?\d+(?: +-?\d+)+", l["text"].strip())]
        rows.sort(key=lambda l: l["bbox"][1])
        values = [l["text"].split() for l in rows]
        if len(rows) < 2 or len(set(map(len, values))) != 1:
            pending.append(("math", box, "matrix row shape ambiguous", {}))
            continue
        source = "\n".join(l["text"] for l in lines if l in selected)
        span = _unique_span(markdown, source)
        lhs_text = ""
        if span is None:
            from mdaddict.geometry_mapping import owned_span
            from mdaddict.native_math import render_row, AmbiguousMath
            left_sides = [l for l in lines if l["bbox"][2] <= box[0] + 1 and
                          box[1] <= l["bbox"][1] <= box[3] and "=" in l["text"] and l.get("chars")]
            if len(left_sides) == 1:
                lhs = left_sides[0]
                native = [c for c in lhs["chars"] if c["c"].strip()]
                size = max(c["size"] for c in native)
                baseline = next(c["origin"][1] for c in native if c["size"] == size)
                try:
                    lhs_text = render_row(native, baseline, size)
                    span = owned_span(markdown, native + [c for l in selected for c in l["chars"]], lines)
                except AmbiguousMath:
                    span = None
        if span is None:
            pending.append(("math", box, "matrix source mapping unavailable", {"rows": len(rows), "columns": len(values[0])}))
            continue
        value = "$" + lhs_text + r"\begin{pmatrix}" + r" \\ ".join(" & ".join(row) for row in values) + r"\end{pmatrix}$"
        if right["text"].endswith("."):
            value += "."
        patches.append((*span, value))

    # Unicode vectors use the same script evidence as complete expressions.
    from mdaddict.native_math import vector_atoms, AmbiguousMath
    from mdaddict.geometry_mapping import owned_span
    all_chars = [c for l in lines for c in l.get("chars", []) if c["c"].strip()]
    try:
        vectors = vector_atoms(all_chars)
    except AmbiguousMath as exc:
        vectors = []
        pending.append(("math", _union([l["bbox"] for l in lines]), "vector relationships ambiguous: " + str(exc), {}))
    for value in vectors:
        span = owned_span(markdown, value["chars"], lines)
        if span:
            patches.append((*span, "$" + value["text"] + "$"))
        else:
            pending.append(("math", value["bbox"], "matrix source mapping unavailable", {}))

    # 3. Computer Modern delimiters for 2x2 matrices
    cm_lefts = [l for l in lines if any(("CMEX" in c.get("font", "").upper() or c.get("c") in {"\x06", "\x08", "\x12", "\x14"})
                                        and c.get("c") in {"(", "[", "\x06", "\x08", "\x12", "\x14"} for c in l.get("chars", []))]
    detected_cm = []
    for left in cm_lefts:
        left_c = next(c for c in left["chars"] if ("CMEX" in c.get("font", "").upper() or c.get("c") in {"\x06", "\x08", "\x12", "\x14"})
                      and c.get("c") in {"(", "[", "\x06", "\x08", "\x12", "\x14"})
        rights = [l for l in lines if any(("CMEX" in c.get("font", "").upper() or c.get("c") in {"\x07", "\x09", "\x13", "\x15"})
                                          and c.get("c") in {")", "]", "\x07", "\x09", "\x13", "\x15"} for c in l.get("chars", []))
                  and l["bbox"][0] > left_c["bbox"][0] and abs(l["bbox"][1] - left_c["bbox"][1]) < 25]
        if not rights:
            continue
        right = min(rights, key=lambda l: l["bbox"][0])
        right_c = next(c for c in right["chars"] if ("CMEX" in c.get("font", "").upper() or c.get("c") in {"\x07", "\x09", "\x13", "\x15"})
                       and c.get("c") in {")", "]", "\x07", "\x09", "\x13", "\x15"})
        box = (left_c["bbox"][0] - 1, min(left_c["bbox"][1], right_c["bbox"][1]) - 2,
               right_c["bbox"][2] + 1, max(left_c["bbox"][3], right_c["bbox"][3]) + 25)
        selected = [l for l in lines if _inside(l["bbox"], box)]
        inner_chars = []
        for l in selected:
            for c in l.get("chars", []):
                if c["c"] not in {"\x06", "\x07", "\x08", "\x09", "\x12", "\x13", "\x14", "\x15", "(", ")", "[", "]"} and c["c"].strip():
                    inner_chars.append(c)
        if not inner_chars:
            continue
        sorted_chars = sorted(inner_chars, key=lambda c: (c["origin"][1], c["bbox"][0]))
        rows = []
        for c in sorted_chars:
            if not rows or abs(c["origin"][1] - rows[-1][0]["origin"][1]) > 3:
                rows.append([c])
            else:
                rows[-1].append(c)
        if len(rows) == 2:
            values = []
            for row in rows:
                row_cols = []
                for c in sorted(row, key=lambda c: c["bbox"][0]):
                    if not row_cols or c["bbox"][0] - row_cols[-1][-1]["bbox"][2] > 3.0:
                        row_cols.append([c])
                    else:
                        row_cols[-1].append(c)
                row_vals = ["".join(c["c"] for c in col).replace("−", "-").replace("–", "-") for col in row_cols]
                values.append(row_vals)
            if all(len(r) == 2 for r in values) and all(re.fullmatch(r"-?[0-9a-zA-Z\\]+", token) for r in values for token in r):
                matrix_val = r"\begin{pmatrix}" + r" \\ ".join(" & ".join(r) for r in values) + r"\end{pmatrix}"
                box_center_y = (box[1] + box[3]) / 2
                lhs_cands = [l for l in lines if l["bbox"][2] <= box[0] + 5 and abs(l["bbox"][1] - box[1]) < 30 and l["bbox"][0] < box[0]]
                lhs = min(lhs_cands, key=lambda l: (abs((l["bbox"][1] + l["bbox"][3]) / 2 - box_center_y), box[0] - l["bbox"][2])) if lhs_cands else None
                detected_cm.append({"box": box, "matrix_val": matrix_val, "lhs": lhs, "selected": selected})

    for start, end, value in sorted(patches, reverse=True):
        markdown = markdown[:start] + value + markdown[end:]
    cm_count = 0
    if detected_cm:
        from mdaddict.geometry_mapping import apply_owned_expressions
        expressions = []
        if all(m["lhs"] for m in detected_cm):
            from mdaddict.native_math import render_row, AmbiguousMath
            for m in detected_cm:
                lhs_chars = [c for c in m["lhs"]["chars"] if c["c"].strip()]
                size = max(c["size"] for c in lhs_chars)
                baseline = next(c["origin"][1] for c in lhs_chars if c["size"] == size)
                try:
                    lhs_text = render_row(lhs_chars, baseline, size)
                except AmbiguousMath:
                    continue
                owned = [c for l in m["selected"] + [m["lhs"]] for c in l["chars"]]
                expressions.append({"bbox": m["box"], "axis": m["lhs"]["chars"][0]["origin"][1],
                                    "chars": owned, "text": "$" + lhs_text + " " + m["matrix_val"] + "$"})
            markdown, applied = apply_owned_expressions(markdown, expressions, lines)
        else:
            applied = []
        cm_count = len(applied)
        applied_boxes = [e["bbox"] for e in applied]
        for m in detected_cm:
            if m["box"] not in applied_boxes:
                pending.append(("math", m["box"], "matrix expression mapping ambiguous", {}))

    return markdown, pending, len(patches) + cm_count


def _drawing_regions(drawings, tables):
    # Connected vector components, not drawing count, indicate figure content.
    groups = []
    for drawing in drawings:
        box = tuple(drawing["rect"])
        if any(_inside(box, table) for table in tables):
            continue
        matched = [g for g in groups if _touch(g[0], box, 3)]
        items = list(drawing.get("items", []))
        if matched:
            for group in matched:
                groups.remove(group)
                box = _union([box, group[0]])
                items.extend(group[1])
        groups.append((box, items))
    result = []
    for box, items in groups:
        horizontal = [item for item in items if item[0] == "l"
                      and abs(item[1].y - item[2].y) < 1 and abs(item[1].x - item[2].x) > 25]
        vertical = [item for item in items if item[0] == "l"
                    and abs(item[1].x - item[2].x) < 1 and abs(item[1].y - item[2].y) > 8]
        shaped = any(item[0] in ("c", "re", "qu") for item in items)
        levels = {round(item[1].y / 2) for item in horizontal}
        if len(levels) >= 2 and vertical and shaped:
            result.append(("circuit", box, "connected wires and gate-like shapes need topology review", {}))
        elif len(horizontal) >= 2 and shaped and box[3] - box[1] > 12:
            result.append(("circuit", box, "wire and gate-like vector component", {}))
    return result


def _swallows(start, end, box, lines, markdown):
    return any(not _touch(line["bbox"], box, 1) and (span := _unique_span(markdown, line["text"]))
               and start <= span[0] < end for line in lines)


def _expand_formula_paragraph(markdown, start, end):
    """Include a short formula block, and stop when the block becomes prose."""
    para_start = markdown.rfind("\n\n", 0, start)
    para_start = 0 if para_start < 0 else para_start + 2
    para_end = markdown.find("\n\n", end)
    para_end = len(markdown) if para_end < 0 else para_end
    paragraph = markdown[para_start:para_end]
    words = re.findall(r"[A-Za-z]{4,}", paragraph)
    if para_end - para_start > 500 or len(words) >= 3:
        return start, end
    return para_start, para_end


def _locate_region(box, lines, markdown):
    selected = [line for line in lines if _touch(line["bbox"], box, 1)]
    if selected:
        source = "\n".join(line["text"] for line in selected)
        grouped = _unique_span(markdown, source)
        if grouped:
            return grouped
        spans = []
        for line in selected:
            visible = "".join(char for char in line["text"] if ord(char) >= 32)
            if not visible.strip():
                continue  # Dropped extensible glyphs cannot veto a located formula.
            span = _unique_span(markdown, line["text"])
            if span:
                spans.append(span)
        if spans:
            start, end = min(item[0] for item in spans), max(item[1] for item in spans)
            expanded = _expand_formula_paragraph(markdown, start, end)
            if not _swallows(*expanded, box, lines, markdown):
                return expanded
            if (start, end) != expanded and not _swallows(start, end, box, lines, markdown):
                return start, end
    elif lines:
        following = sorted((line for line in lines if line["bbox"][1] > box[3]), key=lambda line: line["bbox"][1])
        if following:
            span = _unique_span(markdown, following[0]["text"])
            if span:
                return span[0], span[0]
        preceding = [line for line in lines if line["bbox"][3] < box[1]]
        if preceding:
            span = _unique_span(markdown, max(preceding, key=lambda line: line["bbox"][3])["text"])
            if span:
                return span[1], span[1]
    return None


def _extensible_glyph_regions(lines):
    """Local crops for math glyphs the Markdown adapter cannot encode.

    Subset Computer Modern extension fonts often arrive as control characters.
    Their character codes are not a stable Unicode map, so the crop is held
    instead of being transcribed. Nearby math-only lines stay in the same crop.
    """
    pending = []
    for line in lines:
        odd = [char for char in line["chars"] if any(ord(ch) < 32 for ch in char["c"])]
        if not odd:
            continue
        box = _union([char["bbox"] for char in odd])
        height = max(box[3] - box[1], 8)
        band = (box[0] - 2, box[1] - height, box[2] + 90, box[3] + height)
        extra = [other["bbox"] for other in lines
                 if other is not line and _touch(other["bbox"], band, 0)
                 and not re.search(r"[A-Za-z]{4,}", other["text"])]
        if extra:
            box = _union([box, *extra])
        pending.append(("math", box, "mathematical glyph has no Unicode mapping", {}))
    return pending


def analyze_page(page, native_markdown: str, get_found_tables=None, *, recovered_math=()) -> PageAnalysis:
    """Return deterministic edits and disjoint regions requiring visual evidence.

    get_found_tables: a lazy, memoized find_tables() call shared with the
    caller's own table handling, so the expensive geometric scan runs at most
    once per page, and only on a page that actually has drawings to check.
    """
    get_found_tables = get_found_tables or (lambda: None)
    labels = _baseline_superscript_labels(page)
    if labels:
        native_markdown = unwrap_baseline_superscripts(native_markdown, labels)
    raw = page.get_text("rawdict")
    lines, drawings = _lines(page, raw), page.get_drawings()
    from mdaddict.native_math import glyph_key
    recovered_keys = {glyph_key(c) for e in recovered_math for c in e["chars"]}
    recovered_boxes = [e["bbox"] for e in recovered_math]
    if recovered_keys:
        retained = []
        for line in lines:
            chars = [c for c in line["chars"] if glyph_key(c) not in recovered_keys]
            if chars:
                retained.append({**line, "chars": chars, "text": "".join(c["c"] for c in chars),
                                 "bbox": _union([c["bbox"] for c in chars])})
        lines = retained
    images = page.get_image_info()
    markdown, table_boxes, table_pending, table_count = _ruled_tables(lines, drawings, native_markdown)
    markdown, matrix_pending, matrix_count = _matrices(lines, markdown)

    # Unmatched glyphs must survive so unreadable content remains quarantined.
    page_box = tuple(page.rect) if hasattr(page, "rect") else (0.0, 0.0, 612.0, 792.0)
    # Share the caller's lazy table scan; pages without drawings need no scan.
    all_table_boxes = (_table_boxes(get_found_tables) if drawings else []) + table_boxes
    fraction_bars = [bar for bar in _fraction_segments(drawings, raw, page_box)
                     if not any(_inside((bar[0], bar[1], bar[2], bar[1]), table) for table in all_table_boxes + recovered_boxes)]
    markdown, fraction_pending, fraction_count, fraction_boxes = _fractions(lines, fraction_bars, markdown)
    # Fraction rules cannot also become alphabetic overlines.
    segments = [bar for bar in _segments(drawings)
                if not any(_touch((bar[0], bar[1], bar[2], bar[1]), box, 0)
                           for box in fraction_boxes + [r[1] for r in fraction_pending])]
    markdown, pending, _, resolved = _overlines(lines, segments, markdown)
    pending.extend(table_pending + matrix_pending + fraction_pending)
    resolved += table_count + matrix_count + fraction_count + len(recovered_math)
    if not any(line["text"].strip() for line in lines):
        return PageAnalysis(markdown, [Region("page", "page", page_box, 0, len(markdown), markdown,
                                             reason="no native text layer")], resolved)
    for kind, box, reason, constraints in _drawing_regions(drawings, all_table_boxes + recovered_boxes):
        labels = [line["bbox"] for line in lines if line["bbox"][0] >= box[0] - 30
                  and line["bbox"][2] <= box[2] + 30 and line["bbox"][1] >= box[1] - 2
                  and line["bbox"][3] <= box[3] + 2]
        pending.append((kind, _union([box] + labels), reason, constraints))
    for info in images:
        box = tuple(info["bbox"])
        if info.get("width", 0) <= 1 or info.get("height", 0) <= 1 or min(box[2] - box[0], box[3] - box[1]) <= 3:
            continue
        if (box[2] - box[0]) * (box[3] - box[1]) >= 400:
            pending.append(("page", box, "raster content has no trustworthy native transcription", {}))
    if "\ufffd" in markdown and not pending:
        pending.append(("page", page_box, "unreadable native glyphs", {}))
    pending.extend(_extensible_glyph_regions(lines))
    regions = []
    for kind, box, reason, constraints in sorted(pending, key=lambda r: (r[1][1], r[1][0])):
        span = (0, len(markdown)) if box == page_box else _locate_region(box, lines, markdown)
        if span is None:
            span = (len(markdown), len(markdown))
            reason += "; native region mapping unavailable"
        start, end = span
        regions.append(Region(f"region-{len(regions) + 1}", kind, box, start, end, markdown[start:end],
                              reason=reason, constraints=constraints))
    # Merge shared source spans, retaining all reasons and conservative scope.
    # A crop that could not be tied to Markdown must not absorb the page.
    merged = []
    for region in sorted(regions, key=lambda r: (r.start, -r.end)):
        if (merged and region.start <= merged[-1].end and region.start != region.end
                and merged[-1].start != merged[-1].end):
            prior = merged[-1]
            prior.end = max(prior.end, region.end)
            prior.bbox = _union([prior.bbox, region.bbox])
            prior.text = markdown[prior.start:prior.end]
            prior.reason += "; " + region.reason
            if prior.kind != region.kind:
                prior.kind = "page"
        else:
            merged.append(region)
    return PageAnalysis(markdown, merged, resolved)
