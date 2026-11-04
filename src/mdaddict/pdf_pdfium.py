"""Permissive PDF → Markdown path using pypdfium2 + pypdf forms.

Does not use PyMuPDF. Layout/math geometry recovery remains on the optional
pymupdf path. Text is retained, while uninterpreted math/vector structure is held.
"""
from __future__ import annotations

from pathlib import Path

from mdaddict.strategy import ExtractionIssue, SourceBlock, SourceLocator, figure, normalize


def _page_text(page) -> str:
    textpage = page.get_textpage()
    try:
        return textpage.get_text_bounded() or ""
    finally:
        textpage.close()


def _render_png(page, dpi: int) -> bytes:
    scale = min(max(dpi, 72) / 72, 2400 / max(page.get_size()))
    bitmap = page.render(scale=scale)
    try:
        with bitmap.to_pil() as pil:
            import io
            stream = io.BytesIO()
            pil.save(stream, format="PNG")
            return stream.getvalue()
    finally:
        bitmap.close()


def convert_pdf(adapter, path: Path) -> str:
    import pypdfium2
    from pypdfium2 import raw as pdfium
    from mdaddict.extract_offline import pdf_math_present
    from mdaddict.pdf_forms import load_forms, form_markdown

    forms = load_forms(adapter, path)
    blocks = []
    offset = 0
    try:
        doc = pypdfium2.PdfDocument(str(path))
    except pypdfium2.PdfiumError as error:
        message = str(error).lower()
        if "password" in message or "encrypt" in message:
            raise ValueError("Encrypted PDF: provide an unlocked copy") from error
        raise
    with doc:
        page_count = len(doc)
        adapter.check_pages(page_count)
        for idx in range(page_count):
            page = doc[idx]
            try:
                source = SourceLocator("page", idx + 1)
                block_id = f"page:{idx + 1}"
                method = "native"

                def issue(code, message, severity="review", element=""):
                    message = f"page {idx + 1}: {message}"
                    adapter.warn(message)
                    adapter.issues.append(ExtractionIssue(
                        code, message, SourceLocator("page", idx + 1, element), [block_id], severity))

                raw = _page_text(page)
                images, structure = False, False
                try:
                    for obj in page.get_objects():
                        if obj.type == pdfium.FPDF_PAGEOBJ_IMAGE:
                            images = True
                        elif obj.type != pdfium.FPDF_PAGEOBJ_TEXT:
                            structure = True
                except (pypdfium2.PdfiumError, ValueError, RuntimeError):
                    issue("pdf_layout_unresolved", "page-object inspection failed; structure remains unverified", "unresolved")
                if structure:
                    # No new fraction/table recognizer: vector paths or Form
                    # XObjects may encode relationships absent from plain text.
                    # This deliberately also holds decorative vector content.
                    issue("pdf_layout_unresolved", "vector or nested content may encode math/table relationships absent from plain text", "unresolved")

                if adapter.options.ocr == "force" or (len(raw.strip()) < 20 and images):
                    if adapter.options.ocr == "off":
                        text = figure(f"page {idx + 1}: scan requires OCR")
                        issue("pdf_scan_unresolved", "scan unresolved (--ocr off)", "unresolved")
                    else:
                        method = "ocr"
                        text = adapter.ocr_image(_render_png(page, max(adapter.options.dpi, 200)),
                                                 f"page {idx + 1}")
                        issue("pdf_ocr_review", "OCR transcription requires source review")
                else:
                    text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
                    if not text and images:
                        text = figure(f"page {idx + 1}: embedded visual content not transcribed")
                        issue("pdf_figure_unresolved", "embedded images may contain additional information",
                              "unresolved")
                    elif not text:
                        text = "<!-- blank page or unresolved vector-only content -->"
                        issue("pdf_vector_unresolved", "vector-only content needs vision review", "unresolved")
                    else:
                        # Preserve intentional blank lines; collapse only pure form-feed noise.
                        text = text.replace("\x0c", "\n")
                        if images:
                            text += "\n\n" + figure(f"page {idx + 1}: embedded visual content not transcribed")
                            issue("pdf_figure_unresolved",
                                  "embedded images may contain additional information", "unresolved")
                    if "\ufffd" in text:
                        issue("pdf_glyph_unresolved", "unreadable glyphs; use OCR or AI", "unresolved")

                if pdf_math_present(text) or "^" in text or "_" in text:
                    issue("pdf_math_unresolved", "mathematical notation requires verification of formula relationships on the PDFium text path", "unresolved")

                if images or structure or any(i.source.index == idx + 1 and i.severity == "unresolved" for i in adapter.issues):
                    asset = adapter.image_evidence.register(_render_png(page, 120), source, block_id, f"Page {idx + 1} visual context")
                    text += f"\n\n![{asset.description}](asset:{asset.asset_id})"
                text += form_markdown(forms, idx + 1)
                chunk = normalize(f"<!-- page: {idx + 1} -->\n\n{text.strip()}")
                adapter.source_blocks.append(
                    SourceBlock(block_id, "page", source, offset, offset + len(chunk), method))
                offset += len(chunk) + 2
                blocks.append(chunk)
            finally:
                page.close()
    return "\n\n".join(blocks)
