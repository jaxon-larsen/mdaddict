# mdaddict target plan

Approved direction for the finished package (2026-10-23), with input breadth
expanded by the user on 2026-10-27. Dated bake-off and reuse receipts remain
evidence; this file is the forward plan. The [v1 formulation](v1-formulation-2026-10-27.md)
sets out the implementation boundary. Video uses existing caption/audio paths;
visual-video extraction is outside this first milestone.

## Product

mdaddict is an **offline-first conversion shell**: local files to Markdown for
AI and wiki ingestion, with inspectable extraction and optional
developer-controlled repair.

The first usable website must cover the formats supported by MarkItDown and
the other selected tools. Maintain a versioned capability catalog and delegate
the broader inputs through explicit adapters. Offline defaults, optional
online/media behavior and the small public core remain requirements. Broad
coverage is a planned milestone, not current implemented/verified capability.

It is not a general MarkItDown replacement, not a Docling/Marker layout stack,
and not a learning-content generator.

### Own permanently

- Simple conversion API (path today; bytes/stream only if product need appears).
- Consistent result: Markdown, source locations / character spans, extraction
  methods, actionable issues, content hashes, cache identity.
- Offline defaults and optional format extras.
- Repair orchestration when the caller supplies an adapter: region selection,
  verification rounds, budgets, patch checks, caching.
- Tests that decide whether conversion preserves instructional meaning for
  downstream wiki/claims work.

### Delegate permanently

- Document parsing, layout recognition, OCR, and ordinary format conversion to
  maintained libraries (or small, license-clear copied slices when install would
  be mostly unused machinery).
- Transport, credentials, and model choice for any optional AI call.

### Do not build into the default product

- Always-on LLM or VLM conversion.
- Torch / Docling / Marker (or similar) in the default `[pdf]` or `[all]` path.
- Public pluggable `backend=docling|marker|markitdown` surface; format routing
  stays internal. Selected MarkItDown delegation now has an explicit product need.
- Implicit network access, media-service selection or unbounded archive recursion.
  EPUB, mail, URLs, archives and the remaining selected-tool format families are
  included in the first website's capability plan.
- Endless custom PDF geometry/math rule growth when a simpler library path
  exists.
- Large table libraries (for example pdfplumber-scale trees) in default `[pdf]`
  merely for GFM pipe cosmetics.

## Quality bar for downstream AI use

Preserve instructional text, reading order, table **cell values and their
row/column/header relationships, including empty cells**, equation
**meaning**, and honest unresolved holds. Do not chase layout cosmetics,
decorative figures, or competitor-style confidence theaters.

**Priority:** accuracy of that Markdown, then conversion speed. Reject
**unneeded** install bloat (especially ML in the default PDF extra). Absolute
minimum wheel size is secondary.

Phase “good enough to pause mdaddict work”:

1. Offline suites pass or residuals are explicitly accepted holds.
2. Default PDF stack is permissive (no AGPL in `[pdf]`).
3. The versioned first-website format catalog has configured delegated routes,
   explicit omissions and passing format-family acceptance cases.
4. Beating MarkItDown/Docling/Marker on a shared corpus is nice, not a gate.

## Dependency layout (end state)

| Extra | Purpose |
|---|---|
| *(core)* | Standard library only; plain text-like formats |
| `[pdf]` | **pypdfium2 + pypdf + Pillow** — default PDF |
| `[pdf-pymupdf]` | Optional PyMuPDF / PyMuPDF4LLM for hard layout/math/render until removed |
| `[office]` | python-pptx, openpyxl, lxml; equations via focused OMML (vendored/copied parsers) |
| `[html]` | markdownify; Pandoc remains for complex HTML and DOCX fallback |
| `[images]` | Pillow; system Tesseract for OCR |
| `[all]` | PDFium + Office/HTML/images; excludes the optional PyMuPDF stack and mandatory Torch/Docling/Marker |

The table above describes existing extras. The broader formulation proposes
separate extended-format, acquisition and media integrations; their exact extras
and manifests are not implemented yet. Installing dependencies must not itself
enable network access or select an inference service.

System tools stay external: Pandoc (DOCX / complex HTML / unsupported OMML),
Tesseract (OCR).

### Copy vs install

- Prefer installing a maintained public API when it covers the need.
- Copy and lightly adjust only small, dependency-light, license-clear modules
  when that is clearly better than importing a bloated tree (OMML pattern:
  provenance, hashes, notices ship with the package).
- Do not fork whole competitor converters.

### PDF policy

- Default engine: **pypdfium2**; forms: **pypdf**.
- `ExtractOptions.pdf_backend`: `auto` | `pdfium` | `pymupdf`.
- `auto`: pdfium when it is the only stack; if both extras are installed, keep
  PyMuPDF until callers set `pdfium` (transition). End state: pdfium-only
  default installs, PyMuPDF optional or gone.
- GFM pipe syntax is presentation; cell boundaries, relationships, empties,
  repetition and spans are the acceptance bar. Plain cell-word presence is insufficient.
- PDFium holds unverified vector/nested content and recognized mathematical
  notation. Decorative vectors can also trigger a hold; this guard does not
  certify arbitrary text-only layout or formulas.
- PDF AI repair currently requires explicit PyMuPDF selection plus the optional
  `[pdf-pymupdf]` extra. A provider on the PDFium path raises an actionable error.
- The education application explicitly opts into `[all,pdf-pymupdf]`; public
  `[all]` remains permissive-only.
- Retire or shrink custom native-math/geometry rules when the default engine
  makes them redundant; do not add new rule *classes* without a downstream
  gold gap that a library cannot cover more simply.

## Models and mdaddict (LLM policy)

**mdaddict must not depend on an LLM.**

| Situation | Prefer | Avoid |
|---|---|---|
| Digital PDF / Office / HTML with extractable text | Deterministic native / library conversion | Any neural model |
| Scans, screenshots, embedded picture text | **Local OCR** (Tesseract or similar) | LLM “describe the page” as primary extraction |
| Hard layout / difficult scans (optional extra) | Offline **layout/OCR** packages with explicit install and RAM gates | Always-on VLM in default path |
| Pictured equations | OCR / specialized math OCR, or **hold** + optional bounded repair | LLM as the main converter |
| Flagged uncertain regions | Optional **developer-supplied** adapter (LLM or otherwise) behind repair budgets, verification, and patch checks | Silent model rewrites of whole documents |

Rationale: extraction must preserve meaning for claims, not generate study text.
LLMs invent and normalize. Project live-repair pilots did not earn a mandatory
model path. Speed, offline use, and install size all favor deterministic plus
narrow OCR/layout over chat or vision-language models in the hot path.

Language models remain appropriate for host-application wiki proposals,
verification and grading under application policy. That does not
pull an LLM into mdaddict’s default conversion.

## Implementation sequence (remaining)

The [existing-corpus comparison](pdf-corpus-2026-10-23.md) now measures 29 reviewed
pages from 16 PDFs. PDFium matches the text/order sentinels but misses the 21
structured equation targets and six table/matrix targets. Keep the compatibility
path while evaluating library-backed structural extraction. The table experiment
below addresses relationships on these existing failing controls.
The [LiteParse evaluation](liteparse-evaluation-2026-10-23.md) matches 26/54
content checks with OCR off: it recovers the simple table, but leaves the
structured-math gap and introduces reading-order/stale-form regressions. Keep it
as an evaluation candidate. The [dedicated-table evaluation](table-library-evaluation-2026-10-23.md)
now tests pdfplumber and Camelot: line-based profiles recover the ordinary grid
and merged/empty-cell controls, but match only 1/6 existing targets. Network
adds borderless-table support with a prose false detection and a larger install.
Keep these as optional candidates; current evidence does not justify another
default dependency or broad code port. Prioritize demonstrated safety defects
and the source-to-wiki flow. Model downloads and backend switching remain separate.

The [decimal preservation guard](numeric-guard-2026-10-23.md) now holds a proven
compatibility conversion defect before dependent claims can publish. All content
verdicts remain unchanged; compatibility holds are 16/29 in the fresh corpus run.
The [numbered-column correction](reading-order-2026-10-23.md) then resolves the
ordinary multi-column mismatch by reusing the existing PPTX geometry/numbering
planner with unique PDF paragraph ownership. Compatibility now matches 44/54
content targets, with 16/29 pages held and no unheld mismatches among the selected
checks. Complex layouts, remaining held targets and manual review are still
unverified. Continue with retained-source-to-wiki acceptance before adding more
parser dependencies. The user subsequently authorized the isolated
[local OCR/model comparison](ocr-benchmark-2026-10-24.md), including downloads
and CPU inference. That evaluation supports optional specialist reuse while
preserving the native fast path; it does not authorize production model
integration or cloud calls. Its partial coverage and source-bound review
limitations remain explicit.

The [Linux website pipeline trial](website-pipeline-2026-10-26.md) now measures
100 target page cases and actual API job/cache/review behavior at 1/2/4 clients.
Native extraction remains fast; automatic layout plus specialist formula OCR
provides useful proposals but still produces wrong or malformed expressions.
Keep this evaluation-only and preserve holds. Before a public website, prioritize
bounded queuing, overall job deadlines and cancellation; then add an explicitly
optional repair adapter with candidate output separate from canonical Markdown.
Neither this trial nor its narrow source checks certify full-page accuracy.

The [matched converter comparison](converter-head-to-head-2026-10-26.md) adds
MarkItDown and four Unstructured profiles on those same 100 cases, plus an
installed-wheel native baseline. Shared strict matches are 39/85 for native,
22/85 for MarkItDown and 33–37/85 for Unstructured; text-format sensitivity and
partial gold remain explicit. MarkItDown recovers three table controls; the
heavy Unstructured layout profile recovers none of the strict table/matrix
targets. Keep the conversion shell and pursue bounded table-library reuse;
these results do not establish automatic mathematical fidelity or justify a
wholesale replacement. Competitor API integration remains unmeasured.

1. Keep ordinary PDF/Office/HTML on the permissive, measured paths; expand gold
   only for source-backed downstream defects.
2. Harden bounded job execution before production model integration. Reuse the
   specialist public APIs through an explicit optional adapter; retain review holds.
3. Force `pdf_backend=pdfium` in application settings when textbook math either
   ports, is held honestly, or no longer needs PyMuPDF.
4. Remove `pdf-pymupdf` from the recommended default story once residuals are
   accepted or recovered without AGPL.
5. Optional later: thin table structuring without heavy table extras; bytes/stream
   API only if product need appears.
6. Do not authorize Docling/Marker model downloads for production unless a
   measured offline extra is explicitly approved.

## Related evidence

- [Package comparison](package-comparison-2026-10-23.md)
- [Reuse decisions](reuse-decisions-2026-10-23.md) /
  [reuse implementation](reuse-implementation-2026-10-23.md)
- [PDF bake-off](pdf-bakeoff-2026-10-23.md) /
  [PDF backend switch](pdf-backend-2026-10-23.md)
- [Existing PDF corpus comparison](pdf-corpus-2026-10-23.md)
- [LiteParse evaluation](liteparse-evaluation-2026-10-23.md)
- [Dedicated table APIs](table-library-evaluation-2026-10-23.md)
- [Decimal preservation guard](numeric-guard-2026-10-23.md)
- [Numbered PDF column ordering](reading-order-2026-10-23.md)
- [Local OCR and model benchmark](ocr-benchmark-2026-10-24.md)
- [Linux website pipeline evaluation](website-pipeline-2026-10-26.md)
- [Matched converter comparison](converter-head-to-head-2026-10-26.md)
- [Proposed v1 formulation](v1-formulation-2026-10-27.md)
