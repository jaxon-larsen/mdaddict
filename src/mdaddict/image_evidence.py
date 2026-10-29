"""Job-local image inventory and OCR reuse; image bytes are never persisted here."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import math
import re

from mdaddict.strategy import SourceLocator


@dataclass
class ImagePassage:
    text: str
    method: str
    code: str
    messages: list[str]


class ImageEvidence:
    def __init__(self):
        self.records: dict[str, dict] = {}
        self.ocr_text: dict[str, str] = {}
        self.ocr_runs = 0
        self.ocr_reuses = 0

    @staticmethod
    def view(data: bytes, crop: tuple[float, float, float, float]) -> bytes:
        if not all(math.isfinite(v) for v in crop) or crop[0] + crop[2] >= 1 or crop[1] + crop[3] >= 1:
            raise ValueError("Invalid embedded image crop")
        if not any(crop):
            return data
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Image exceeds 40 megapixels")
            # Negative margins extend the canvas; they reveal no additional
            # source pixels. Positive margins exclude hidden source content.
            left, top, right, bottom = (max(0, value) for value in crop)
            bounds = (round(image.width * left), round(image.height * top),
                      round(image.width * (1 - right)), round(image.height * (1 - bottom)))
            if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                raise ValueError("Embedded image crop has no visible pixels")
            stream = io.BytesIO()
            image.crop(bounds).save(stream, format="PNG")
            return stream.getvalue()

    def describe(self, engine, data: bytes | None, alt: str, location: str,
                 source: SourceLocator, block_id: str | None, *, crop=(0., 0., 0., 0.), context="") -> ImagePassage:
        image_hash = hashlib.sha256(data).hexdigest() if data else None
        method = "ai" if data and getattr(engine, "provider", None) is not None else "ocr" if data and engine.options.ocr == "force" else "native"
        # Reference-only extraction must still handle raster formats Pillow
        # cannot decode (e.g. Office metafiles). No visible view is processed.
        view = self.view(data, crop) if data and method != "native" else data
        view_hash = hashlib.sha256(view).hexdigest() if view and (method != "native" or not any(crop)) else None
        before = len(engine.warnings)
        reused = False
        code = None
        if method == "ai":
            from mdaddict.office_image_repair import repair_image
            text, method, code, reused = repair_image(engine,self,view,alt,location,source,block_id,context,view_hash)
        elif method == "ocr" and view_hash in self.ocr_text:
            text = self.ocr_text[view_hash]
            reused = True
            self.ocr_reuses += 1
            engine.warn(f"{location}: reused OCR transcription; equations, table structure and diagrams require review")
        else:
            text = engine.describe_image(view, alt, location)
            # Cache OCR only: it is context-free. Vision prompts include source
            # context, so identical image bytes alone cannot reuse AI responses.
            if method == "ocr":
                self.ocr_text[view_hash] = text if not text.startswith("<!-- fig:") else ""
                self.ocr_runs += 1
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if method == "ocr" and code is None:
            from mdaddict.strategy import figure
            # Retain the visual reference even when OCR recovers words: diagrams
            # and mathematical relationships are not established by word OCR.
            text = figure(alt or location) + ("\n\n### Unverified image text\n\n" + text if text and not text.startswith("<!-- fig:") else "")
        messages = engine.warnings[before:] or [f"{location}: {method} image content requires source review"]
        if code is None and method in {"native","ocr"}:
            from mdaddict.office_image_repair import mathematical
            pictured_math = mathematical(alt) or (method=="ocr" and mathematical(text)) or (
                bool(re.search(r"\b(?:figure|image|pictured)\b",context,re.I)) and mathematical(context))
            if pictured_math:
                code = "equation_unresolved"
                messages.append(f"{location}: pictured mathematics remains unverified")
        record = self.records.setdefault(image_hash or f"missing:{source.unit}:{source.index}:{source.element}",
                                         {"image_sha256": image_hash, "occurrences": []})
        record["occurrences"].append({"source": asdict(source), "block_id": block_id,
                                      "alt": alt, "crop": list(crop), "view_sha256": view_hash,
                                      "method": method, "ocr_reused": reused,
                                      "semantic_status": "untranscribed" if method == "native" else "needs_review",
                                      "representation": "source_reference" if method == "native" else "unverified_text",
                                      "retention": "source_reference_only"})
        return ImagePassage(text, method, code or ("figure_unresolved" if method == "native" else "figure_transcription_review"), messages)

    def metadata(self) -> dict:
        return {"images": list(self.records.values()),
                "image_processing": {"unique_images": len(self.records),
                                     "occurrences": sum(len(row["occurrences"]) for row in self.records.values()),
                                     "ocr_runs": self.ocr_runs, "ocr_reuses": self.ocr_reuses}}
