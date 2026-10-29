"""Only reorder numbered sequences whose disjoint geometry corroborates order.

Shared by slide shapes and native PDF text regions. This is not a general layout
model. Unnumbered layouts stay in source order; conflicting layouts need review.
"""
from __future__ import annotations
import re


def order_shapes(shapes):
    shapes = list(shapes)
    numbered, other = [], []
    for shape in shapes:
        text = shape.text.strip() if getattr(shape, "has_text_frame", False) else ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        matches = [re.match(r"^(\d+)[.)]\s+", line) for line in lines]
        if any(matches):
            if not all(matches):
                return shapes, "Mixed numbered and unnumbered text in one shape"
            numbers = [int(m.group(1)) for m in matches]
            numbered.append((shape, numbers))
        else:
            other.append(shape)
    if len(numbered) < 2:
        return shapes, None
    if any(abs(float(getattr(s, "rotation", 0))) > .01 for s in shapes):
        return shapes, "Rotated shapes have ambiguous reading order"
    if any(getattr(s, "shape_type", None) == 6 for s in shapes):
        return shapes, "Group transforms have unsupported reading order"
    nums = [n for _, values in numbered for n in values]
    if sorted(nums) != list(range(1, len(nums) + 1)):
        return shapes, "Numbering conflicts or gaps require reading-order review"
    box = lambda s: (s.left, s.top, s.left+s.width, s.top+s.height)
    for i, (left, _) in enumerate(numbered):
        a = box(left)
        for right, _ in numbered[i+1:]:
            b = box(right)
            if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                return shapes, "Numbered shapes overlap"
    columns = []
    for entry in sorted(numbered, key=lambda e: (e[0].left, e[0].top, e[0].shape_id)):
        s, _ = entry
        if columns and s.left < max(e[0].left+e[0].width for e in columns[-1]):
            columns[-1].append(entry)
        else:
            columns.append([entry])
    if len(columns) > 2:
        return shapes, "More than two numbered columns require review"
    spatial = [entry for column in columns for entry in sorted(column, key=lambda e: (e[0].top, e[0].left, e[0].shape_id))]
    if [n for _, values in spatial for n in values] != list(range(1, len(nums)+1)):
        return shapes, "Numbering and column geometry disagree"
    top = min(s.top for s, _ in numbered)
    bottom = max(s.top+s.height for s, _ in numbered)
    if any(s.top < bottom and s.top+s.height > top for s in other):
        return shapes, "Other shapes interrupt the numbered reading region"
    before = [s for s in other if s.top+s.height <= top]
    after = [s for s in other if s.top >= bottom]
    return before + [s for s, _ in spatial] + after, None
