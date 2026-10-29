# PDF bake-off — 2026-10-23

Offline comparison used to choose mdaddict’s permissive PDF default. Harness:
`education/engine/tools/evaluate_pdf_bakeoff.py`. Raw outputs under ignored
`education/engine/out/pdf-bakeoff/`. No production backend change is implied by
this document alone; see the implementation receipt when the switch lands.

**Review correction:** the measurements below describe the original probe. Its
table check accepted words anywhere on the page; that does not verify table
meaning. The hardened check now requires row/column relationships, empty cells
and repetition through the existing structural comparator. PDFium also now
retains source-linked holds for unverified math/vector/nested structure. Original
pass counts and timings are historical, not release or current hold acceptance.

## Scope

- Gold: invented ordinary-pdf controls (multi-column order, simple table,
  two-page prose), held-out `conditions.pdf`, and `form-valid` text value
  `Specimen 42` in the education benchmark fixtures.
- Scoring: coverage / order / text / table cell presence. Not source-span parity.
- Network blocked. Marker and Docling attempted model/network access and were
  recorded as unavailable under that constraint.
- Priority from product grill: **accuracy, then speed**; reject **unneeded**
  bloat (ML in the default `[pdf]` extra). Absolute minimum install size is
  secondary.

## Results (warm median ms; 3 repeats; Windows)

| Backend | Passes / 7 | Typical warm ms | Peak RSS MiB | Notes |
|---|---:|---:|---:|---|
| mdaddict (PyMuPDF4LLM) | 6 | 13–37 | 67 | Failed multi-column footer placement (steps 4–6 after footer). Only backend with form value + GFM tables on this set. |
| markitdown | 5 | 9–15 | 147 | Prose OK; multi-column order fail; no form value. |
| pymupdf4llm direct | 5 | 5–12 | 58 | Same pattern as MarkItDown; AGPL stack. |
| **pypdfium2 text** | 5 | **1–4** | **41** | Best multi-column order; prose OK; table **cells** present (not GFM pipes); no form value. Permissive. |
| pypdf text | 5 | 1–3 | 50 | Same profile as PDFium; slightly different table/form gaps. Permissive. |
| pdfplumber text | 4 | 3–6 | 52 | Multi-column fail; cells present without GFM table unit. Larger install tree. |
| docling-pdf | 0 | — | 530 | Needs torch / model fetch; blocked offline. |
| marker-fast | 0 | — | 488 | Import pulls network for weights; blocked offline. |

Dependency inventory (installed files in the evaluation venv, exploratory):
pypdfium2 ~7–8 MiB with binary; pdfplumber tree much larger; marker-pdf pulled
Torch and related ML (~hundreds of MiB). Exact MiB are in `dependency_inventory.json`.

## Post-implementation check

`mdaddict` with `pdf_backend=pdfium` on the same seven cases: **6/7 pass**
(multi-column, prose, held-out, forms). The remaining mismatch is GFM pipe-table
*structure* on `simple-table` while cell text is present. This is insufficient
for acceptance: row/column relationships are not established by cell presence.
Warm times in that original probe were ~7–12 ms; peak RSS ~51 MiB.

## Decision

1. **Default PDF engine → pypdfium2** (plus existing **pypdf** for AcroForm
   inspection). Meets downstream text/order/cell-content needs on this corpus,
   is markedly faster, and avoids AGPL PyMuPDF in the default extra.
   Implemented in [pdf-backend-2026-10-23.md](pdf-backend-2026-10-23.md).
2. **Retain PyMuPDF4LLM as optional** `pdf-pymupdf` for hard layout/math/OCR
   rendering paths until those recoveries are ported or held.
3. **Do not** make Docling/Marker default or required; they need ML weights and
   failed the offline bake-off. Revisit only with authorized offline models.
4. **Forms** stay on the pypdf inspector (remove the PyMuPDF “quick” probe).
5. **GFM table pipes** are presentation; cell relationships and empty cells are the gate.
   Optional later: light table structuring without pulling pdfplumber into
   default `[pdf]`.
6. **Multi-column**: PDFium beat current mdaddict on the control; accept that
   as evidence for the switch, and keep the fixture as a regression.

## Limits

- No textbook equation pages in this bake-off run (local originals optional via
  `--source`; not required for the permissive default decision).
- Marker/Docling accuracy with downloaded weights is unknown here.
- Source-location and issue-contract parity are not established by text-only
  probes. See the backend receipt for the conservative holds and forced-PDFium
  controls added after review.

## Reproduction

```powershell
# Evaluation interpreter already has markitdown/docling-slim/pypdfium2/etc.
C:\Users\Jaxon\coding\mdaddict\out\reuse-evaluation\venv\Scripts\python.exe `
  engine\tools\evaluate_pdf_bakeoff.py `
  --out engine\out\pdf-bakeoff `
  --baseline-python engine\.venv\Scripts\python.exe `
  --repeat 3
```
