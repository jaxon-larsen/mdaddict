"""Local-first, budgeted Office-image transcription with source verification."""
from __future__ import annotations
import io
import re
import shutil

from mdaddict.fidelity import repair_regions
from mdaddict.fidelity_geometry import Region
from mdaddict.strategy import figure


def mathematical(text):
    # OCR often loses the very fraction/ket glyphs that should trigger repair.
    # Explicit quantum-math context still evidences instructional mathematics.
    return bool(re.search(r"[=√∑∫]|\\(?:frac|sqrt|ket|bra)|\b(?:equation|formula|numerator|denominator|fraction|radical|qubit|superposition|amplitude|bloch)\b", text, re.I))


def image_tiles(data):
    from PIL import Image
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError("Image exceeds 40 megapixels")
        tiles = []
        def split(image):
            stream = io.BytesIO()
            image.save(stream, "PNG")
            encoded = stream.getvalue()
            if len(encoded) <= 3_500_000:
                tiles.append(encoded)
            elif min(image.size) < 24:
                raise ValueError("Office image cannot fit without losing glyph detail")
            elif image.height >= image.width:
                mid = image.height//2
                split(image.crop((0,0,image.width,mid)))
                split(image.crop((0,mid,image.width,image.height)))
            else:
                mid = image.width//2
                split(image.crop((0,0,mid,image.height)))
                split(image.crop((mid,0,image.width,image.height)))
            if len(tiles) > 20:
                raise ValueError("Office image exceeds 20 lossless tiles")
        split(source)
        return tiles, source.size


def repair_image(engine, inventory, view, alt, location, source, block_id, context, view_hash):
    marker = figure(alt or location)
    text = ""
    reused = False
    if engine.options.ocr != "off" and (shutil.which("tesseract") or engine.options.ocr == "force"):
        if view_hash in inventory.ocr_text:
            text = inventory.ocr_text[view_hash]
            inventory.ocr_reuses += 1
            reused = True
        else:
            try:
                text = engine.ocr_image(view, location)
                inventory.ocr_text[view_hash] = text if not text.startswith("<!-- fig:") else ""
                inventory.ocr_runs += 1
            except (RuntimeError, ValueError) as error:
                engine.warn(f"{location}: local OCR unavailable: {error}")
    math = mathematical(text + "\n" + alt + "\n" + context)
    # Readable OCR remains unverified text. It is not a diagram interpretation.
    if engine.options.ai_mode == "auto" and text.strip() and not text.startswith("<!-- fig:") and not math:
        engine.warn(f"{location}: local image transcription requires source review")
        return marker+"\n\n### Unverified image text\n\n"+text, "ocr", "figure_transcription_review", reused
    unit = (source.unit, source.index)
    if unit not in engine.office_ai_units and len(engine.office_ai_units) >= engine.options.max_ai_pages:
        engine.warn(f"{location}: AI page/slide budget exhausted")
        return marker+("\n\n### Unverified image text\n\n"+text if text else ""), "ocr" if text else "native", "ai_page_budget_deferred", reused
    engine.office_ai_units.add(unit)
    try:
        images, (width,height) = image_tiles(view)
        region = Region("office-image", "math" if math else "figure", (0,0,width,height), 0,len(text),text,True,
            "pictured instructional content requires transcription", {"source_context":context, "location":location,
            "source": {"unit":source.unit,"index":source.index,"element":source.element}, "block_id":block_id})
        patches, reason = repair_regions(engine.runner, [region], images)
        if reason:
            engine.warn(f"{location}: {reason}")
            return marker+("\n\n### Unverified image text\n\n"+text if text else ""), "ocr" if text else "native", "equation_unresolved" if math else "vision_region_unresolved", reused
        engine.warn(f"{location}: verified image transcription still requires source review")
        return marker+"\n\n"+patches[0][1], "ai", "figure_transcription_review", reused
    except (ValueError, OSError) as error:
        # Provider configuration failures must still reach the caller.
        from mdaddict.ai import ProviderError
        if isinstance(error, ProviderError) and error.configuration:
            raise
        engine.warn(f"{location}: {error}")
        return marker, "native", "equation_unresolved" if math else "vision_region_unresolved", reused
