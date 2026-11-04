# mdaddict target plan

Approved direction for the finished package (2026-10-23), with input breadth
expanded on 2026-10-27 and quality-input coverage prioritized on 2026-11-03.
Dated bake-off and reuse receipts remain
evidence; this file owns the current priorities and acceptance bar. The
[v1 formulation](v1-formulation-2026-10-27.md) records the earlier family inventory
and implementation boundary. Video uses existing caption/audio paths;
visual-video extraction is outside this first milestone.

## Product

mdaddict is an **offline-first conversion shell**: local files to Markdown for
AI and wiki ingestion, with inspectable extraction and optional
developer-controlled repair.

Maximize the range of inputs that can yield useful, faithful source content for
the education app. MarkItDown input breadth is the baseline, not the ceiling;
reuse additional maintained readers when representative fixtures demonstrate
useful extraction. The intended advantage is broad conversion plus stronger
instructional fidelity, provenance and actionable uncertainty. Breadth must be
available through the application, not only listed in a package catalog.

Keep offline defaults, optional online/media behavior and the small public core.
Format extras can carry justified dependencies; a small core must not become a
reason to reject useful optional input families. mdaddict delegates maintained
parsers and is not a learning-content generator. It does not promise universal
layout recovery or compatibility with every third-party plugin/cloud service.

### Own permanently

- Simple conversion API; path input exists, while bytes/stream and CLI stdin
  handling are explicit input-parity gaps to resolve.
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

## Input coverage and parity

This section owns current coverage limits and the forward acceptance bar.
The [v1 formulation](v1-formulation-2026-10-27.md#full-format-catalog) supplies
the broader family inventory. Pin the MarkItDown release/revision and enabled
extras when preparing the parity matrix; the existing delegation pin is 0.1.9.
The 2026-11-03 review inspected current upstream converter sources, but did not
run a new parity benchmark. Installed third-party plugins and optional cloud
enrichment are separate scopes that must be identified before comparing results.

| Input family | Extensions | Upstream MarkItDown 0.1.9 Converter | mdaddict Implemented Route | Configured Prerequisites / Provider | Fixture Evidence | App Exposure | Known Omissions & Limits |
|---|---|---|---|---|---|---|---|
| Text & Code | .md, .txt, .py, .json, .yaml, .xml, .csv, etc. | PlainTextConverter | Native stdlib reader | Python stdlib | Existing test_format_parity, test_ingestion | Upload dropzone & file picker | Preserves source characters; no layout reconstruction |
| Delimited Tables | .csv, .tsv, .tab | CsvConverter | Native stdlib csv parser | Python stdlib | Existing test_ingestion, test_format_parity | Upload dropzone & file picker | Tabular structure preserved; formulas not evaluated |
| HTML / Web | .html, .htm, .xhtml | HtmlConverter | Markdownify / Pandoc bridge | markdownify or Pandoc | Existing test_html_backend | Upload dropzone & file picker | External resources and dynamic scripts not fetched |
| PDF Documents | .pdf | PdfConverter | pdfium / pypdfium2 / PyMuPDF | pypdfium2 (or PyMuPDF stack) | Existing test_pdfium, test_pdf_order, test_pdf_numeric | Upload dropzone & file picker | 2-D math and scanned vectors require review |
| Word Documents | .docx | DocxConverter | Native Pandoc bridge | python-docx / lxml, Pandoc fallback | Existing test_synthetic_office, packaging baseline | Upload dropzone & file picker | Visuals unresolved; macros/drawings not certified |
| Presentations | .pptx | PptxConverter | python-pptx native reader | python-pptx, lxml, PIL | Existing test_synthetic_office, procedures.pptx | Upload dropzone & file picker | Shapes/visuals require source review; no bitmap sidecars |
| Modern Spreadsheets | .xlsx | XlsxConverter | openpyxl native reader | openpyxl | Existing test_ingestion | Upload dropzone & file picker | Formulas as expressions; styling/charts omitted |
| Legacy Spreadsheets | .xls | XlsConverter | Delegated MarkItDown XlsConverter | markitdown==0.1.9, pandas, xlrd | test_xls_meaningful_content (synthetic BIFF8) | Capability-driven upload | Cached cell values only; formulas and drawings omitted |
| Electronic Books | .epub | EpubConverter | Delegated MarkItDown EpubConverter | markitdown==0.1.9 | test_epub_spine_content_is_retained | Capability-driven upload | Spine text only; embedded visual/media omitted |
| Notebooks | .ipynb | IpynbConverter | Delegated MarkItDown IpynbConverter | markitdown==0.1.9 | test_notebook_delegates_code_language | Capability-driven upload | Code/markdown cells only; outputs/attachments omitted |
| Outlook Mail | .msg | OutlookMsgConverter | Delegated MarkItDown OutlookMsgConverter | markitdown==0.1.9, olefile | test_msg_meaningful_content (synthetic OLE) | Capability-driven upload | Plain text body only; attachments not extracted |
| MIME Mail & Signatures | .eml, .p7s | None (mdaddict native) | Bounded container mail parser | Python stdlib email | test_email_keeps_body, test_detached_binary_signature | Capability-driven upload | Plain/HTML body only; signature verification omitted |
| RSS / Atom Feeds | .rss, .atom | RssConverter | Delegated MarkItDown RssConverter | markitdown==0.1.9 | test_feed_uses_maintained_reader | Capability-driven upload | Feed item body/titles only; dynamic links not fetched |
| Container Archives | .zip | ZipConverter | Bounded member dispatcher | Python stdlib zipfile | test_archive_rebases_spans, recursive budget tests | Capability-driven upload | Supported members only; recursive budget limits apply |
| Subtitles / Captions | .srt, .vtt | None (mdaddict native) | Local subtitle reader | pysubs2 | test_local_captions_have_exact_times | Capability-driven upload | Transcript text and segment timing only |
| Images (Raster) | .png, .jpg, .jpeg, .tiff, .bmp, .webp, etc. | ImageConverter | Pillow / Tesseract | PIL, optional Tesseract | Existing test_ingestion, test_ocr_benchmark | Upload dropzone & file picker | OCR review needed; diagrams/spatial context uncertified |
| HEIF Images | .heic, .heif | None | Pillow / pillow-heif | pillow_heif, PIL | test_heif_codec_is_explicit | Capability-driven upload | Codec requires pillow-heif; OCR needed for text |
| Legacy Office | .doc, .ppt | None | LibreOffice headless bridge | LibreOffice (soffice/libreoffice) | test_legacy_readers | Capability-driven upload (disabled if missing) | Intermediate conversion; requires external LibreOffice |
| Extended Readers | .odt, .rtf, .org, .adoc, .tex, etc. | None | Pandoc CLI bridge | Pandoc | test_legacy_readers | Capability-driven upload (disabled if missing) | Requires Pandoc; format-specific parser behavior |
| Audio Files | .wav, .mp3, .flac, .ogg, etc. | AudioConverter | Explicit audio provider adapter | Explicit provider with 'audio' modality | test_media_requires_explicit_modality | Unavailable (no app audio provider configured) | Speech transcript only; requires configured audio provider |
| Video Containers | .mp4, .mov, .webm, etc. | None | ffmpeg audio demux + audio provider | ffmpeg, audio provider | test_media_requires_explicit_modality | Unavailable (no app audio provider configured) | Audio track only; video frames/visuals not extracted |
| Web URLs | None (HTTP) | Wikipedia/Bing converters | Bounded HTTP acquisition | Python urllib, network permitted | test_url_retains_exact_bytes | Remote import view | Static artifact only; dynamic/linked content omitted |
| YouTube URLs | None (URL) | YouTubeConverter | youtube-transcript-api | youtube_transcript_api, network permitted | test_youtube_keeps_caption_times | Remote import view | Captions only; video visuals/audio track not analyzed |
| Streams, Stdin & Raw Bytes | None | Supported in MarkItDown | None (deferred gap) | None | None | None | Public API is path-based; streams/stdin deferred |
| Content / MIME Detection | None | Supported in MarkItDown | None (deferred gap) | None | None | None | Extensionless / unfamiliar-suffix detection deferred |

The education upload control is capability-driven, exposing configured local formats
(including ZIP, EPUB, XLS, IPYNB, MSG, and subtitles) dynamically when their prerequisites
are installed. Audio and video remain unavailable until an application audio provider
is configured. The application's capability endpoint represents both installed dependencies
and actually wired providers, driving truthful upload choices and admission gating.

For each family and input method, record separately: implemented route,
configured prerequisites/provider, accepted fixture coverage, app exposure, and
known fidelity/omission limits. `ready` means prerequisites were found, not that
content quality passed. Extension recognition, metadata-only output, empty output,
or an entirely unresolved result cannot count as successful content parity.

Require representative source-bound positives, malformed/unsupported negatives,
and known-omission cases. Compare meaningful content and structure under matched
offline/provider settings. Preserve errors and holds in the denominator. A format
with incomplete acceptance remains explicitly pending; a successful small control
does not certify every codec, document variant or source page.

Sequence: freeze the parity inventory; complete missing family/variant fixtures
and useful maintained-reader integrations; connect actual app capabilities to
upload/import choices; resolve input-method/detection gaps; then deepen the
instructional-fidelity improvements below. Critical source-corruption defects
remain eligible for immediate fixes throughout. Local AI is unavailable; source,
adapter and deterministic verification work can proceed, while inference and
live media quality require separate execution instructions and recorded results.

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
4. Input-family/method parity against the pinned baseline and app exposure are
   acceptance gates. Comparative fidelity gains require source-reviewed evidence;
   historical selected-check scores do not establish superiority on all inputs.

## Dependency layout (end state)

| Extra | Purpose |
|---|---|
| *(core)* | Standard library only; plain text-like formats |
| `[pdf]` | **pypdfium2 + pypdf + Pillow** — default PDF |
| `[pdf-pymupdf]` | Optional PyMuPDF / PyMuPDF4LLM for hard layout/math/render until removed |
| `[office]` | python-pptx, openpyxl, lxml; equations via focused OMML (vendored/copied parsers) |
| `[html]` | markdownify; Pandoc remains for complex HTML and DOCX fallback |
| `[images]` | Pillow; system Tesseract for OCR |
| `[extended]` | Pinned MarkItDown readers for XLS/EPUB/IPYNB/MSG/feeds |
| `[captions]` | Local SRT/WebVTT parsing |
| `[online]` | Explicit YouTube caption acquisition |
| `[heif]` | Explicit HEIC/HEIF codec integration; outside `all` |
| `[all]` | PDFium + Office/HTML/images/extended/captions; excludes PyMuPDF, HEIF and mandatory model stacks |

These extras and the capability catalog are implemented; installed availability
and acceptance coverage vary. Audio/video require a supplied audio provider;
there is no configured application transcription path yet. Installing dependencies
must not itself enable network access or select an inference service.

System tools stay external: Pandoc (DOCX / complex HTML / additional readers /
unsupported OMML), Tesseract (OCR), LibreOffice (legacy Office bridges), and
ffmpeg (video audio extraction). Their presence does not configure a provider.

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

1. Close the [input coverage and parity](#input-coverage-and-parity) gaps first:
   record a pinned baseline, accept representative variants, expose package
   capabilities in the app, and resolve input-method/detection gaps.
2. Deepen instructional fidelity on demonstrated source defects: default PDF
   equations, table/matrix relationships, reading order, and code/qualifier
   preservation. Reuse established APIs; keep uncertainty explicit.
3. Improve provenance and issue locality so verified surrounding content remains
   useful without clearing unresolved regions or dependent content.
4. Account for native slide shapes/PDF vector diagrams and figure-caption links,
   not only embedded bitmap occurrences. A locator/hash is not visual meaning.
5. Evaluate comparative gains in preserved content, unflagged critical errors,
   usable content after holds, review effort, runtime and dependency footprint.
   Report safety separately from successful recovery.
6. Complete the permissive PDF cutover when residuals are recovered or explicitly
   accepted; remove the application's PyMuPDF requirement only with evidence.
   Optional specialist integrations require their own measured acceptance; no
   model downloads or inference are authorized by this plan.

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
