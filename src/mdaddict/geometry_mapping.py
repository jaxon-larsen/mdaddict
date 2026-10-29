"""Conservative ownership checks for native geometry replacements."""
from collections import Counter
import re


def owned_span(markdown, chars, lines=None):
    """Find one contiguous span containing exactly the owned native glyphs.

    The adapter can reorder two-dimensional text. Compare glyph multiplicities,
    never approximate words or discard extra tokens. Only font-proven glyphs may
    account for a replacement character in Markdown. Duplicate matches stay held.
    """
    source = "".join(c.get("display", c.get("native", c["c"])) for c in chars)
    if any(c.get("display") == "\ufffd" and not c.get("proven") for c in chars):
        return None
    ignored = "*_" + ("" if "[" in source or "]" in source else "[]")
    ignored = "".join(c for c in ignored if c not in source)
    ligatures = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}

    def tokens(text):
        return [(v, i) for i, c in enumerate(text) for v in ligatures.get(c, c)
                if not v.isspace() and v not in ignored]

    expected = Counter(v for v, _ in tokens(source))
    length = sum(expected.values())
    if length < 3:
        return None
    # Separately retained omissions must not be confused with the original body.
    cutoff = markdown.find("### Source text recovered from native layer")
    body = markdown[:cutoff] if cutoff >= 0 else markdown
    begin, finish = 0, len(body)
    if lines is not None:
        from mdaddict.fidelity_geometry import _unique_span
        owned = {id(c) for c in chars}
        y0, y1 = min(c["origin"][1] for c in chars), max(c["origin"][1] for c in chars)
        outside = [l for l in lines if not any(id(c) in owned for c in l["chars"])]
        for preceding in (True, False):
            candidates = [l for l in outside if l["chars"] and
                          (max(c["origin"][1] for c in l["chars"]) < y0 - 1 if preceding else
                           min(c["origin"][1] for c in l["chars"]) > y1 + 1)]
            candidates.sort(key=lambda l: l["bbox"][3] if preceding else -l["bbox"][1], reverse=True)
            anchor = None
            for line in candidates:
                text = "".join(c.get("display", c["c"]) for c in line["chars"])
                if len(text.strip()) >= 4 and re.search(r"[A-Za-z]", text):
                    anchor = _unique_span(body, text)
                    if anchor:
                        break
            if candidates and anchor is None:
                return None
            if anchor:
                if preceding:
                    begin = anchor[1]
                else:
                    finish = anchor[0]
        if begin >= finish:
            return None
        body = body[begin:finish]
    observed = tokens(body)
    counts, matches = Counter(), []
    for end, (value, _offset) in enumerate(observed):
        counts[value] += 1
        if end >= length:
            old = observed[end - length][0]
            counts[old] -= 1
            if not counts[old]:
                del counts[old]
        if end + 1 >= length and counts == expected:
            start = observed[end - length + 1][1]
            stop = observed[end][1] + 1
            if any(mark in body[start:stop] for mark in ("```", "~~~", "<!--", "$")):
                continue
            # Formatting around the first/last glyph belongs to this span too.
            while start and body[start - 1] in ignored:
                start -= 1
            while stop < len(body) and body[stop] in ignored:
                stop += 1
            matches.append((start, stop))
    return (matches[0][0] + begin, matches[0][1] + begin) if len(matches) == 1 else None


def apply_owned_expressions(markdown, expressions, lines=None):
    """Patch isolated expressions, or a small interleaved display group, once."""
    patches, used = [], set()
    expressions = sorted(expressions, key=lambda e: (e["axis"], e["bbox"][0]))
    for count in range(1, min(8, len(expressions)) + 1):
        for i in range(len(expressions) - count + 1):
            group = expressions[i:i + count]
            if any(id(e) in used for e in group):
                continue
            if any(b["axis"] - a["axis"] > 45 for a, b in zip(group, group[1:])):
                continue
            chars = [c for e in group for c in e["chars"]]
            if len({id(c) for c in chars}) != len(chars):
                continue
            span = owned_span(markdown, chars, lines)
            if span is None or any(max(span[0], p[0]) < min(span[1], p[1]) for p in patches):
                continue
            value = "\n\n".join(e["text"] for e in group)
            patches.append((*span, value))
            used.update(id(e) for e in group)
    for start, end, value in sorted(patches, reverse=True):
        markdown = markdown[:start] + value + markdown[end:]
    return markdown, [e for e in expressions if id(e) in used]
