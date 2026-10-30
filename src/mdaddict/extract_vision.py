"""Deterministic-first extraction with optional provider-neutral region repair."""
from __future__ import annotations

import io
import re
from pathlib import Path

from mdaddict.extract_offline import OfflineExtractor, image_png, native_tables, missing_source_blocks, pdf_math_present
from mdaddict.strategy import ExtractionIssue, SourceBlock, SourceLocator, figure, normalize
from mdaddict.fidelity_geometry import analyze_page, Region
from mdaddict.fidelity import repair_regions, apply_patches
from mdaddict.vision_runtime import VisionRunner, PROMPT_REVISION, SYSTEM_PROMPT, BudgetExhausted
from mdaddict.ai import ProviderError

# Compatibility exports for callers of the old shared Bedrock helpers.
VISION_MAX_TOKENS_CAP = 8192
AI_RENDER_DPI_CAP = 300


def vision_max_tokens(options):
    return options.max_tokens


def ai_render_dpi(options):
    return options.dpi


def render_region(page, bbox, dpi):
    """Split lossless crops spatially rather than reducing thin glyphs to JPEG."""
    import pymupdf
    rect = pymupdf.Rect(bbox) & page.rect
    if rect.is_empty:
        raise ValueError("Empty source region")
    pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72, dpi / 72), clip=rect, alpha=False)
    data = pix.tobytes("png")
    if len(data) <= 3_500_000:
        return [data]
    if min(rect.width, rect.height) < 24:
        raise ValueError("Region cannot fit image budget without losing detail")
    if rect.height >= rect.width:
        mid = (rect.y0 + rect.y1) / 2
        halves = [(rect.x0, rect.y0, rect.x1, mid), (rect.x0, mid, rect.x1, rect.y1)]
    else:
        mid = (rect.x0 + rect.x1) / 2
        halves = [(rect.x0, rect.y0, mid, rect.y1), (mid, rect.y0, rect.x1, rect.y1)]
    images = []
    for half in halves:
        images.extend(render_region(page, half, dpi))
    if len(images) > 20:
        raise ValueError("Region exceeds 20 image tiles")
    return images


def render_page_for_ai(page, dpi):
    images = render_region(page, tuple(page.rect), dpi)
    if len(images) != 1:
        raise ValueError("Page requires tiled region request")
    return images[0], "png"


def strip_outer_markdown_fence(text):
    match = re.fullmatch(r"```(?:markdown|md)\s*\n([\s\S]*?)\n```", text.strip())
    return match.group(1) if match else text


def build_patch_user_text(location, native_markdown):
    excerpt = native_markdown[:2500]
    if len(native_markdown) > 2500:
        excerpt += "\n<!-- native truncated for prompt budget -->"
    return f"Source location: {location}.\nNative draft (untrusted):\n{excerpt}"


def page_difficulty_score(*, text, image_count, drawing_count):
    # Compatibility utility only; production scheduling uses unresolved geometry.
    return (50 if len(text.strip()) < 40 else 0) + (30 if pdf_math_present(text) else 0) + (40 if '\ufffd' in text else 0) + min(image_count, 8) * 3 + (25 if drawing_count > 8 else 0)


def select_ai_pages(scored, *, ai_mode, max_ai_pages):
    eligible = scored if ai_mode == "all" else [x for x in scored if x[1] > 0]
    ranked = sorted(eligible, key=lambda x: (-x[1], x[0]))
    return sorted(x[0] for x in ranked[:max_ai_pages]), sorted(x[0] for x in ranked[max_ai_pages:])


class VisionExtractor(OfflineExtractor):
    name = "vision"
    def __init__(self, options=None, *, provider):
        super().__init__(options)
        self.provider = provider
        self.model_id = provider.model_id
        self.region_cache_dir = None
        self.office_ai_units = set()
        self.runner = VisionRunner(provider, self.options)
        self.usage = self.runner.usage

    def _get_client(self):
        # Kept for callers that use the previous inspection seam.
        return self.provider

    def _transcribe_image(self, data, location, *, fmt="png", native_markdown=""):
        response, _ = self.runner.request([data], build_patch_user_text(location, native_markdown),
            "image", system=SYSTEM_PROMPT + "\nReturn Markdown only for this standalone image.")
        return strip_outer_markdown_fence(response.text)

    def describe_image(self, data, alt, location, asset_id: str | None = None) -> str:
        if not data:
            return super().describe_image(data, alt, location, asset_id=asset_id)
        return figure(alt or location, asset_id=asset_id) + "\n\n" + self._transcribe_image(image_png(data), location)

    def _image(self, path):
        if path.suffix.lower() in {".heic", ".heif"}:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        from PIL import Image
        chunks = []
        with Image.open(path) as source:
            self.check_pages(getattr(source, "n_frames", 1))
            for idx in range(self.pages):
                source.seek(idx)
                stream = io.BytesIO()
                source.save(stream, "PNG")
                if idx >= self.options.max_ai_pages:
                    text = figure("AI page budget exhausted")
                    self.issues.append(ExtractionIssue("ai_page_budget_deferred", "Frame remains unresolved", SourceLocator("frame", idx+1), severity="unresolved"))
                else:
                    text = self._transcribe_image(image_png(stream.getvalue()), f"frame {idx+1}")
                chunks.append(f"<!-- frame: {idx+1} -->\n\n{text}")
        return "\n\n".join(chunks)

    def _pdf(self, path):
        if self._resolve_pdf_backend() == "pdfium":
            from mdaddict.dependencies import MissingDependencyError
            raise MissingDependencyError(
                "PDF AI repair currently requires pdf_backend='pymupdf' and mdaddict[pdf-pymupdf]. "
                "Omit ai_provider to use offline PDFium conversion; no backend was switched.")
        import pymupdf
        import pymupdf4llm
        from mdaddict.pdf_forms import load_forms, form_markdown
        forms = load_forms(self, path)
        analyses = []
        self.fidelity_records = []
        self.office_ai_units = set()
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                raise ValueError("Encrypted PDF: provide an unlocked copy")
            self.check_pages(len(doc))
            headers = pymupdf4llm.IdentifyHeaders(doc)
            for idx, page in enumerate(doc):
                native = pymupdf4llm.to_markdown(doc, pages=[idx], hdr_info=headers, show_progress=False,
                    write_images=False, embed_images=False, force_text=True)
                table_warnings = []
                # Lazy + memoized: find_tables() is the single most expensive
                # per-page call; native_tables() and analyze_page() share it and
                # it only actually runs on a page that turns out to need it.
                found_tables_cache = {}
                def get_found_tables():
                    if "v" not in found_tables_cache:
                        try:
                            found_tables_cache["v"] = page.find_tables(strategy="lines_strict")
                        except (AttributeError, ValueError, RuntimeError):
                            found_tables_cache["v"] = None
                    return found_tables_cache["v"]
                native = native_tables(native, self.check_cells, table_warnings.append, get_found_tables)
                native = native or page.get_text()
                analysis = analyze_page(page, native, get_found_tables)
                # Missing content or an ambiguous table cannot be treated as clean.
                missing = missing_source_blocks(page, analysis.markdown)
                if (missing or table_warnings) and not analysis.regions:
                    analysis.regions.append(Region(f"p{idx+1}-page", "page", tuple(page.rect), 0,
                        len(analysis.markdown), analysis.markdown, True, "native content or table mapping incomplete", {}))
                if self.options.ai_mode == "all" and not analysis.regions:
                    analysis.regions.append(Region(f"p{idx+1}-page", "page", tuple(page.rect), 0,
                        len(analysis.markdown), analysis.markdown, False, "explicit all-page review", {}))
                analyses.append(analysis)
            # Serial risk-prioritized scheduling makes budget allocation independent
            # of thread completion order and completes a batch before starting more.
            ranked = sorted((i for i,a in enumerate(analyses) if a.regions),
                key=lambda i: (-sum(2 if r.kind in {"math", "circuit"} else 1 for r in analyses[i].regions), i))
            selected = ranked[:self.options.max_ai_pages]
            selected_set = set(selected)
            deferred = [i for i in ranked if i not in selected_set]
            self.selected_pages = sorted(i+1 for i in selected)
            self.deferred_ai_pages = sorted(i+1 for i in deferred)
            methods = ["native"] * len(doc)
            for idx in ranked:
                analysis = analyses[idx]
                page = doc[idx]
                if idx not in selected_set:
                    for region in analysis.regions:
                        self._region_issue(idx, region, "ai_page_budget_deferred", "AI page budget exhausted")
                    continue
                # Batches use one crop per region; large crops are tiled and kept
                # in their own batch to preserve unambiguous image/region mapping.
                batches = []
                ordinary = []
                for region in analysis.regions:
                    try:
                        images = render_region(page, region.bbox, max(200, self.options.dpi))
                        if len(images) > 1:
                            batches.append(([region], images))
                        else:
                            ordinary.append((region, images[0]))
                    except ValueError as error:
                        self._region_issue(idx, region, "vision_region_unresolved", str(error))
                for start in range(0, len(ordinary), 8):
                    batch = ordinary[start:start+8]
                    batches.append(([r for r,_ in batch], [data for _,data in batch]))
                page_patches = []
                for regions, images in batches:
                    patches, reason = repair_regions(self.runner, regions, images)
                    if reason:
                        for region in regions:
                            self._region_issue(idx, region, "vision_region_unresolved", reason)
                    else:
                        page_patches.extend(patches)
                        for region in regions:
                            self._region_issue(idx, region, "ai_transcription_review", "AI region transcription requires source review", severity="review")
                if page_patches:
                    analysis.markdown = apply_patches(analysis.markdown, page_patches)
                    methods[idx] = "ai" if any(r.kind == "page" for r,_ in page_patches) else "mixed"
            chunks = []
            offset = 0
            for idx, analysis in enumerate(analyses):
                text = analysis.markdown + form_markdown(forms, idx+1)
                chunk = normalize(f"<!-- page: {idx+1} -->\n\n{text.strip()}")
                self.source_blocks.append(SourceBlock(f"page:{idx+1}", "page", SourceLocator("page", idx+1), offset, offset+len(chunk), methods[idx]))
                offset += len(chunk)+2
                chunks.append(chunk)
                self.fidelity_records.append({"page": idx+1, "resolved_locally": analysis.resolved,
                    "regions": [{"id": r.id, "kind": r.kind, "bbox": list(r.bbox), "reason": r.reason} for r in analysis.regions]})
            return "\n\n".join(chunks)

    def _region_issue(self, idx, region, code, message, severity="unresolved"):
        self.issues.append(ExtractionIssue(code, message,
            SourceLocator("page", idx+1, "bbox:" + ",".join(f"{v:.2f}" for v in region.bbox)),
            [f"page:{idx+1}"], severity))

    def extract(self, path: Path):
        self.runner = VisionRunner(self.provider, self.options, self.region_cache_dir)
        self.usage = self.runner.usage
        self.selected_pages = []
        self.deferred_ai_pages = []
        self.fidelity_records = []
        self.office_ai_units = set()
        result = super().extract(path)
        result.usage = dict(self.usage)
        result.metadata.update({"model_id": self.model_id, "provider": self.provider.name,
            "provider_settings": self.provider.settings, "prompt_revision": PROMPT_REVISION,
            "ai_pages": self.selected_pages, "ai_pages_deferred": self.deferred_ai_pages,
            "region_cache_hits": self.runner.cache_hits, "vision_calls": self.runner.records,
            "fidelity": self.fidelity_records, "max_ai_requests": self.runner.limit})
        result.metadata["office_ai_units"] = [{"unit":unit,"index":index} for unit,index in sorted(self.office_ai_units)]
        if self.runner.usage["requests"] or self.runner.cache_hits:
            from mdaddict.review import CONTENT_ISSUE_CODES
            # Existing page/picture issues already hold their exact blocks.
            # A redundant document-wide issue would also hold clean native text.
            transcribed = {b.id for b in result.blocks if b.method in {"ai", "mixed"}}
            covered = {bid for issue in result.issues if issue.code in CONTENT_ISSUE_CODES | {"ai_transcription_review", "figure_transcription_review"}
                       for bid in issue.block_ids}
            missing = transcribed - covered
            if missing or (not transcribed and not covered):
                result.issues.append(ExtractionIssue("ai_transcription_review", "AI transcription requires source verification",
                                                     block_ids=sorted(missing)))
        result.refresh_status()
        return result
