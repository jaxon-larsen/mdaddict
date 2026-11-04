"""Shared eligibility policy, including extraction records written by older engines."""
from __future__ import annotations

VISUAL_ISSUE_CODES = frozenset({
    "pdf_figure_unresolved", "pdf_vector_unresolved", "figure_unresolved",
    "shape_geometry_unresolved", "object_unresolved", "docx_object_unresolved",
    "docx_drawing_unresolved", "image_visual_not_transcribed",
})
CONTENT_ISSUE_CODES = frozenset({
    "asset_context_unresolved",
    "equation_unresolved", "equation_placement_unresolved", "pdf_scan_unresolved",
    "pdf_region_unresolved", "pdf_glyph_unresolved", "vision_region_unresolved",
    "pdf_layout_unresolved", "pdf_math_unresolved", "pdf_numeric_unresolved", "pdf_reading_order_unresolved",
    "ai_page_budget_deferred",
    "pdf_form_conflict", "pdf_form_orphan", "pdf_form_structure_unresolved",
    "pdf_form_appearance_mismatch", "pdf_form_unlocated", "pdf_form_unsupported",
})


def _get(issue, key, default=None):
    return issue.get(key, default) if isinstance(issue, dict) else getattr(issue, key, default)


def effective_severity(issue) -> str:
    code = str(_get(issue, "code", "")).lower()
    if code in CONTENT_ISSUE_CODES:
        return "unresolved"
    if code in VISUAL_ISSUE_CODES:
        return "informational"
    return _get(issue, "severity", "review")

