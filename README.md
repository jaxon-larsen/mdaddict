# mdaddict

Offline-first conversion of local files into Markdown, with optional source
locations, extraction issues, and explicitly enabled developer-supplied AI.

This is an unreleased working package; licensing and PyPI publication remain
pending.

## Install from source

```console
git clone https://github.com/jaxon-larsen/mdaddict.git
cd mdaddict
python -m pip install .
python -m pip install '.[all]'
```

The base install uses only the Python standard library. The optional `all` extra
includes the selected local readers and subtitle parser. Pandoc,
LibreOffice, Tesseract and ffmpeg remain separately installed tools. Online
caption retrieval uses a separate `online` extra; media transcription requires
an explicit developer-supplied audio provider.

## Python and command-line API

```python
from mdaddict import to_markdown, extract

markdown = to_markdown("notes.md")
result = extract("document.pdf")
print(result.markdown)
print(result.issues)
```

The base package has no runtime dependencies. Install `mdaddict[pdf]`,
`mdaddict[pdf-pymupdf]`, `mdaddict[office]`, `mdaddict[images]`,
`mdaddict[html]`, or `mdaddict[all]` for additional formats. Default PDF
conversion uses permissive pypdfium2 (+ pypdf for forms). Optional
`pdf-pymupdf` keeps the PyMuPDF4LLM stack for hard layout/math cases
(`ExtractOptions(pdf_backend="pymupdf")` or `--pdf-backend pymupdf`). Ordinary
HTML uses optional Markdownify. Native PowerPoint equations use a bounded,
vendored, standard-library-only OMML parser.
Pandoc is a separate requirement for DOCX, complex HTML (math, merged/nested
tables and certain code cases), and unsupported PowerPoint equation structures.
Existing installations with Pandoc can still convert HTML without the HTML extra.
Tesseract and language data are separate requirements for offline OCR.
OCR defaults to `auto`; `ExtractOptions(ocr="off")` retains current unresolved
markers instead of performing OCR. Nothing downloads tools or models.

`[all]` includes the permissive PDF stack and excludes `[pdf-pymupdf]` and `[heif]`. Install
`mdaddict[all,pdf-pymupdf]` only when explicitly opting into that optional stack.
During the transition, `pdf_backend="auto"` prefers PyMuPDF if it is installed;
otherwise it selects PDFium. Set `pdf_backend="pdfium"` to guarantee that path
in an environment containing both stacks.

`mdaddict FILE` prints Markdown. `--out DIR` enables persistent output/cache,
`--output FILE` exports a Markdown copy, and `--json` prints the structured
result. Without an output directory there are no persistent conversion files.
Temporary processing files may still be used by format adapters.

The Python API ignores provider-selection environment variables. Pass an
`ai_provider` explicitly to enable the shared repair workflow. Source content
is untrusted data, and extraction success does not certify fidelity.

`to_markdown()` and `extract()` both accept `options`, `ai_provider`, `out_dir`,
and `force` keyword arguments. `out_dir` enables the validated Markdown/JSON
cache; `force=True` bypasses its reads. Existing cache implementations are
fingerprinted, so moving/updating the package invalidates old cache entries.
Retained schema-1.0 extraction records still load through `load_extract()`.
The result is serializable with `dataclasses.asdict()`. Its blocks reference
zero-based Unicode code-point offsets with exclusive ends in `result.markdown`.
Diagnostics are advisory evidence about extraction, not application approval or
publication decisions. Temporary native conversion files never modify inputs.

## Broader inputs and explicit acquisition

```python
from mdaddict import capabilities, ingest

catalog = capabilities()  # dependency/provider/network availability; no fetches
archive = ingest("sources.zip")
captions = ingest("captions.vtt")  # requires mdaddict[captions]
snapshot = ingest("https://example.com/document.pdf", kind="url", allow_network=True,
                  out_dir="conversion-output")
video_captions = ingest("YOUTUBE_VIDEO_ID", kind="youtube", allow_network=True)
```

`extended` installs the pinned MarkItDown 0.1.9 readers for XLS, EPUB, IPYNB,
MSG and RSS/Atom, plus selected Wikipedia/Bing HTML snapshot readers. Only
allowlisted converter classes are invoked. The default MarkItDown dispatcher,
its implicit speech service, plugins and cloud document services are not used.
MarkItDown's transitive dependencies are confined to this optional extra.
Mail and bounded ZIP traversal use the standard library. DOC/PPT use a local
LibreOffice bridge; additional document readers use Pandoc (3.10 is the tested
version; older versions may lack readers). `heif` adds the HEIC/HEIF codec as an
explicit opt-in: the upstream binary wheels bundle GPLv2 components. It is
excluded from `all` pending a suitable decoder-build/license decision. See the
[upstream bundled-library notice](https://github.com/bigcat88/pillow_heif/blob/master/LICENSES_bundled.txt).

`mdaddict --capabilities` prints the versioned extension/MIME catalog and current
prerequisites. `ready` means configured prerequisites were found; each row's
`verification` field separately records acceptance status. It does not certify
content fidelity or guarantee that a particular codec/provider can read an input.
`mdaddict URL --kind url --allow-network` and `--kind youtube` explicitly enable
acquisition. No remote fetching occurs for ordinary file conversion.

Remote source snapshots retain origin, final URL, digest and exact downloaded
bytes. Without `out_dir`, bytes are base64 metadata; with it, bytes live under
`.sources/`. YouTube evidence is the structured caption response, not the video
or original caption XML. Existing captions keep supplied timestamps and language
metadata; unavailable captions raise an error. Video visuals remain unresolved.
Remote sources are fetched afresh; their local conversion caches remain bound
to bytes and settings, and origin metadata is isolated from file caches.

For audio, supply an adapter with `modalities = {"audio"}`. Its `AIRequest.media`
contains `MediaAttachment` bytes/MIME/name, and it returns `AIResponse` with
optional `TranscriptSegment(text, start_seconds, end_seconds)` records. Existing
image adapters default to `vision`. Video uses ffmpeg to extract one bounded
mono audio track, then the same explicit provider. No video frames are sent or
invented timestamps added. The adapter owns its model transport timeout;
transcription is one request without automatic retries. A zero request budget
forbids a fresh media transcription. Speech remains subject to source review.

`ExtractOptions(max_archive_members=200, max_archive_depth=3,
max_expanded_mb=500)` bounds shared recursive ZIP/mail traversal. Member names
never become extraction paths. The manifest records hashes, original paths,
individual outcomes and child locators; unsupported members remain partial
results. Delegated documents use whole-document locators. Notebook outputs,
MSG attachments, EPUB visuals and legacy-layout limitations remain explicit
issues. `metadata["ingestion"]` provides the common versioned result summary;
schema 1.0, Markdown spans and existing local APIs remain compatible.

See the [implementation and acceptance receipt](docs/v1-implementation-2026-10-27.md)
for verified families and remaining deployment/quality work.

## Reproduce package verification

Install the development tools (`build`, `twine`, `pytest`), then run:

```console
python tools/verify_distribution.py --profiles core --out out/verification-core
```

The verifier freezes source and tests, builds one wheel/sdist pair, checks
metadata and tests the installed wheel outside the checkout. It retains logs,
artifact SHA-256 values and an input fingerprint in `manifest.json`, and refuses
to overwrite an existing evidence directory. Select a fresh `--out` for each run.
For the complete optional-dependency matrix, use
`--profiles core pdf pdf-pymupdf office images html extended captions heif online all`.
The `all` check requires Pandoc and Tesseract on PATH. The `heif` check is an
explicit codec opt-in; it does not add HEIF to the default `all` dependencies.
CI uses the same command and uploads the receipts. These checks use authored
fixtures and deterministic providers; they make no live model/caption calls.

## Optional AI adapter

Implement `AIProvider` using any API client, local model, or other mechanism:

```python
from mdaddict import AIRequest, AIResponse, ExtractOptions, extract

class MyProvider:
    name = "my-adapter"
    model_id = "my-model"
    settings = {"temperature": 0}
    cache_identity = {"adapter_revision": "1", "model_revision": "my-model-v1"}

    def call(self, request: AIRequest) -> AIResponse:
        # Your implementation sends request.images, request.system,
        # request.prompt and request.max_tokens to the selected model.
        text, input_tokens, output_tokens = call_my_model(request)
        return AIResponse(text, input_tokens=input_tokens, output_tokens=output_tokens)

result = extract("document.pdf", ai_provider=MyProvider(),
                 options=ExtractOptions(max_ai_requests=4))
```

`call_my_model` above is developer-supplied. The adapter owns credentials,
transport timeouts and vendor-specific response decoding. Identity/settings
must be JSON-serializable, contain no secrets, and distinguish any configuration
or implementation change that could change responses. They are retained in
metadata/cache records. `AIResponse.finish_reason` must be `"complete"` for an
accepted response (the default); truncated/blocked responses must use another
value or raise `ProviderError`. Usage counters must be nonnegative integers.
Transport failures can raise `ProviderError(transient=True, retry_after=...)`;
configuration failures use `configuration=True` and propagate to the caller.

mdaddict manages region selection, transcription/verification, retry/request
budgets, response caches, and patch validation. It supplies untrusted source
evidence to the adapter; accepted repairs still retain source-review status.
`max_ai_requests=0` permits compatible cache replay but no new provider calls.
The standalone CLI uses offline conversion. AI adapters are supplied explicitly
through the Python API.

## Direction

The finished-package plan—permissive default PDF, delegated parsers, fidelity
for downstream AI use, and **no LLM dependency** for default conversion—is in
[docs/target-plan.md](docs/target-plan.md).

The [v1 formulation](docs/v1-formulation-2026-10-27.md) plans broad delegated
format support and explicit URL/media acquisition while retaining offline defaults.
These additional integrations are planned; the supported formats below describe
the current implementation.

The [website pipeline evaluation](docs/website-pipeline-2026-10-26.md) measures
native conversion, optional local formula proposals, caching, and API job behavior.
The model path remains experimental and retains source-review holds.
The [matched converter comparison](docs/converter-head-to-head-2026-10-26.md)
adds MarkItDown and Unstructured on identical PDF inputs.

## Supported formats and limits

All existing formats are retained: PDF, PPTX, DOCX, local HTML, text/Markdown,
CSV/TSV, XLSX, and supported raster images. Output uses GitHub-flavored Markdown,
LaTeX math, fenced code, and HTML for tables where required. Diagnostics describe
actual source locations and Unicode offsets, not guessed semantic confidence.
Image export and new output dialects remain deferred. Default `[pdf]` uses
pypdfium2 and pypdf; optional `[pdf-pymupdf]` keeps PyMuPDF for hard cases.
Optional AI repair requires an explicit developer-supplied adapter and is not
part of the default conversion path.

PDFium retains source text but does not reconstruct tables or two-dimensional
equations. Recognized mathematical notation, vector paths, nested PDF content,
and failed object inspection retain source-linked unresolved holds. Decorative
vectors may also be held. Text-only extraction does not prove row/column or
formula relationships, and these checks are not a complete ambiguity detector.
OCR rendering is capped at a 2,400-pixel longest side.

PDF AI repair currently requires both `[pdf-pymupdf]` and
`ExtractOptions(pdf_backend="pymupdf")`. Supplying an AI adapter on the PDFium
path raises an actionable `MissingDependencyError` before conversion or model
calls; it does not select another backend. Omit `ai_provider` for offline PDFium.
AI adapters for other supported formats retain their existing behavior.

The copied Office-math component is attributed in the shipped
[third-party notice](src/mdaddict/_vendor/NOTICE), with its full Apache 2.0
license and [release hashes](src/mdaddict/_vendor/README.md). Its integration
retains source locations, equation diagnostics and unresolved-content handling.
This third-party license does not settle mdaddict's own pending project license.

## Distribution checks

Build with `python -m build .` from the repository root. This builds the
wheel from its source distribution. Validate metadata with
`python -m twine check --strict dist/*`.
`python tests/check_distribution.py --extra core` verifies the installed
wheel outside the checkout. Repeat for `pdf`, `pdf-pymupdf`, `office`, `images`,
`html`, and `all`;
the `all` check requires Pandoc and Tesseract on PATH. The CI matrix covers
Windows/Linux/macOS with Python 3.12/3.13. Declared support and configured CI are
distinct from recorded results. See [release setup](RELEASING.md) for publishing
configuration and remaining release prerequisites.
