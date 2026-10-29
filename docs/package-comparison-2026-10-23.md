# Package comparison — 2026-10-23

The subsequent [reuse decisions](reuse-decisions-2026-10-23.md) add measured
synthetic probes, dependency inventories, narrower Office-math candidates, and
the user's permissive-default licensing requirement. This initial comparison
remains a source/documentation review of the pre-integration implementation.
The later [implementation receipt](reuse-implementation-2026-10-23.md) records
which measured candidates were adopted; statements below about current backends
describe the earlier baseline.

## Assessment

mdaddict has a credible focus: offline file-to-Markdown conversion with small
default dependencies, source-linked extraction issues, and explicit developer
control over AI repair. A speed or accuracy lead has not been established.
This review inspected current primary documentation and repository source; it
did not run competing converters or their benchmarks. Repository default-branch
features can differ from the latest published release.

## Comparable tools

| Tool | Established capabilities | Implication for mdaddict |
|---|---|---|
| markdownify | HTML-to-Markdown conversion, configurable rendering, custom tag converters. Its Python dependencies include Beautiful Soup and six. | A focused HTML backend worth measuring. Our current HTML conversion requires the external Pandoc executable; ordinary HTML is an opportunity to simplify installation. No HTML quality comparison was run. |
| python-docx | A DOCX object model for reading, creating, and updating Word content, including paragraphs, runs, tables, styles, and inline pictures. | A parser building block. A developer still needs Markdown rendering, equation handling, source mapping, and conversion diagnostics. Replacing our DOCX path with it would require substantive fidelity work. |
| pypandoc / Pandoc | Python wrapper around Pandoc, which supports many structured document formats and Markdown dialects. The binary can be installed separately or supplied by pypandoc_binary. | We already use Pandoc directly for DOCX/HTML and Office equations. A wrapper would mainly change discovery and packaging, not the underlying conversion engine. Pandoc itself does not provide a PDF input reader. |
| MarkItDown | Broad LLM-oriented conversion, including Office/PDF/HTML, EPUB, audio, archives, streams, and URLs; format extras and converter plugins; optional AI integrations. | The closest broad API competitor. Its standard result contains Markdown and an optional title; our source-span and issue contract adds detail for review workflows. Its format breadth and extension system exceed ours. |
| Marker | Layout/OCR/math/table processing, image export, structured outputs, batch conversion, optional LLM services. Current source includes fast and balanced modes. | An important difficult-PDF baseline. Fast mode minimizes VLM use and can avoid starting its VLM server on clean documents without equations. Its current base dependencies still include Torch, Transformers, Surya, and vendor SDKs. |
| Docling | A rich document representation, layout/OCR/table processing, broad formats, multiple exports, integrations, and confidence grades. | A stronger structured-document ecosystem than ours. Docling Slim supplies optional components, so comparison must include an appropriately configured slim install. Local model pipelines can run offline after model provisioning. |
| PyMuPDF4LLM / PyMuPDF | Markdown/JSON/text extraction, layout information, image support, and RAG-oriented APIs. Current PyMuPDF 2.0 documentation moves core conversion into Document methods. | A dependency and a competing direct solution. Our pinned PyMuPDF 1.28.2 and PyMuPDF4LLM 0.0.27 path needs a controlled comparison with newer upstream functionality before carrying more overlapping code. |

Sources: [markdownify usage](https://github.com/matthewwithanm/python-markdownify/blob/develop/README.rst)
and [dependencies](https://github.com/matthewwithanm/python-markdownify/blob/develop/pyproject.toml);
[python-docx](https://python-docx.readthedocs.io/en/latest/);
[pypandoc](https://github.com/JessicaTegner/pypandoc) and [Pandoc formats](https://pandoc.org/);
[MarkItDown](https://github.com/microsoft/markitdown),
[dependencies](https://github.com/microsoft/markitdown/blob/main/packages/markitdown/pyproject.toml),
and [result contract](https://github.com/microsoft/markitdown/blob/main/packages/markitdown/src/markitdown/_base_converter.py);
[Marker](https://github.com/datalab-to/marker) and [dependencies](https://github.com/datalab-to/marker/blob/master/pyproject.toml);
[Docling](https://github.com/docling-project/docling),
[Slim](https://github.com/docling-project/docling/tree/main/packages/docling-slim),
[confidence grades](https://docling-project.github.io/docling/concepts/confidence_scores/),
and [offline setup](https://docling-project.github.io/docling/usage/advanced_options/);
[PyMuPDF4LLM API](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html).

## Current strengths

- The base package has zero third-party runtime dependencies. Format libraries
  load lazily; no local ML framework, cloud SDK, model download, or AI account is
  required for native conversion. PDF/Office/image extras add their own footprint.
- The same conversion options support a string-returning convenience API and a
  structured result. Source locators, exact Markdown character spans, issues,
  extraction methods, and hashes help developers inspect uncertain material.
- AI is explicitly supplied through a small provider-neutral call interface.
  The package owns repair selection, transcription/verification rounds, request
  limits, response checks, patch checks, and cache validation. Transport and
  credentials remain developer-owned.
- There is focused native recovery for scientific equations and Office math,
  together with unresolved-content markers and source-based regressions.
  General mathematical accuracy remains unproven.
- Native-first processing avoids mandatory local model inference for ordinary
  supported documents. That is an architectural advantage for deployment;
  comparative latency and throughput remain measurements to make.

Source: `src/mdaddict/{extract,strategy,extract_offline,ai,vision_runtime,fidelity}.py`
and `pyproject.toml`. These are implementation findings, not competitor benchmarks.

## Current weaknesses

- No common-corpus accuracy or speed results exist. Packaging parity and passing
  regression tests cannot establish an overall lead.
- A zero-dependency core is a narrow installation claim. PDF and Office formats
  need substantial native dependencies; DOCX/HTML and PPTX equations need Pandoc,
  and OCR needs Tesseract plus language data. Ordinary embedded Office pictures
  are not automatically OCRed by the offline `auto` mode.
- Coverage is smaller than the broad alternatives: no EPUB, legacy binary
  Office formats, email, audio/video, archive traversal, or URL ingestion. XML
  and similar text extensions are preserved as text, not semantically parsed.
- The public input API accepts paths. It lacks a first-class bytes/stream API,
  converter plugins, batch interfaces, retained-image export, and RAG chunking.
- Heuristic issues are not calibrated confidence scores. They can miss bad
  content or flag acceptable content. The AI verifier also cannot establish
  semantic truth merely by returning an accepted response.
- Source offsets and provenance are useful but not unique. Marker has geometric
  block outputs; Docling has a richer document model and confidence reporting;
  current upstream PyMuPDF offers structured output and grounding features.
- Scientific/PDF recovery logic has accumulated specialized rules. Maintenance
  and repeated upstream extraction need profiling before further optimization.
- Project licensing is undecided. The PDF stack includes PyMuPDF, whose official
  distribution is offered under AGPL and commercial agreements. Treat dependency
  licensing as a release decision requiring review; no legal compatibility
  conclusion is established here. [PyMuPDF licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)

Marker's current source declares Apache 2.0 for code and separate terms for its
model weights. Older descriptions of its code license should not be used for
current comparisons. [Current Marker license description](https://github.com/datalab-to/marker#commercial-usage)

## Recommended next measurements

1. Freeze independently reviewed source cases before running competitors:
   ordinary text/HTML/Office, born-digital PDFs, and difficult scanned/layout/math
   PDFs. Preserve current supported formats; report scores per format and class.
2. Compare MarkItDown for breadth, current PyMuPDF conversion for the native PDF
   baseline, Marker fast/balanced and Docling for difficult PDFs, and
   markdownify/Pandoc for HTML. Use python-docx as a parser baseline rather than
   treating it as an existing full converter.
3. Record clean-environment dependency bytes, model/binary requirements, cold
   startup, warm runtime, peak RAM, pages per second, and supported Python/OS
   combinations. Compare equal hardware and explicit configurations.
4. Score text omissions/additions, reading order, table cells/spans, equation
   meaning, and source-location accuracy. Measure whether issue flags identify
   actual errors, including false positives and missed errors.
5. Keep native/local-model/remote-AI results separate. Count provisioning time
   separately from steady-state runtime, and cache replay separately from fresh
   conversion. Run no paid or provider-backed evaluation without authorization.
6. Use results to decide whether HTML should use markdownify, whether current
   PDF upstream improvements can replace custom logic, and where optional
   specialist engines would improve quality at acceptable dependency cost.

The promising positioning is: **offline-first Markdown conversion for AI
ingestion, with source-linked diagnostics and optional developer-controlled
repair**. Fastest, smallest, and most accurate are goals to measure separately.
