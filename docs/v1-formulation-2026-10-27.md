# mdaddict v1 formulation — 2026-10-27

Status: working v1 boundary following the converter benchmarks. The user has
confirmed that the first usable website must cover all formats supported by
MarkItDown and the other selected tools, with video limited to what is easy to
delegate now. The [implementation receipt](v1-implementation-2026-10-27.md)
records the local ingestion boundary, verification and remaining acceptance work.

## Product and ownership

**mdaddict is an offline-first source-to-Markdown ingestion layer that delegates
format conversion to established tools and returns inspectable source evidence,
explicit omissions, and optional developer-controlled repair.**

The website gets one ingestion boundary for uploaded files, remote sources and
media. Its input catalog is the versioned union of the selected converters'
capabilities. We do not write another parser for each supported format, and
format breadth does not require replacing the better-tested native PDF path.

| Layer | Responsibility |
| --- | --- |
| Website | User/notebook ownership, retained objects, durable jobs, progress, review UI, source viewers and downstream wiki/practice |
| Acquisition adapters | Explicit URL/YouTube retrieval; retain the exact response/transcript and origin metadata |
| mdaddict | Dispatch, normalized result, source locators/spans, hashes, cache identity, issue semantics and repair orchestration |
| Maintained converters | File decoding, OCR, document structure, tables, captions and media transcription |
| Explicit AI/media adapter | Developer-selected local or remote inference, with declared modalities, identity and bounded calls |

The public core stays standard-library-only. Format and online/media dependencies
remain optional extras. The full website installs its selected adapters; a
consumer converting plain text does not inherit their dependencies. Existing
`to_markdown()` / `extract()` calls remain valid. Remote acquisition must be an
explicit operation, rather than a local-file call silently enabling the network.

## Full format catalog

Breadth is in the first website milestone. The catalog must be generated and
checked against pinned converter versions, extensions, MIME types and actual
readers. This is an input-family inventory, not a claim that these integrations
are already implemented or validated.

| Family | Catalog to cover | Delegation direction |
| --- | --- | --- |
| Text/structured text | Plain text/code, Markdown, JSON/JSONL/NDJSON, YAML, XML, RST, Org and other selected reader formats | Standard-library paths, MarkItDown or existing Pandoc readers |
| Documents/presentations | PDF, DOC/DOCX, PPT/PPTX, ODT, RTF and selected document-reader variants | Current native adapters first; existing conversion tools for legacy/additional inputs |
| Tables/spreadsheets | CSV, TSV/TAB, XLS/XLSX | Current CSV/openpyxl paths; delegated legacy spreadsheet reader |
| Web/feeds | HTML/HTM/XHTML, RSS/Atom, ordinary URLs and specialized web-page converters | Explicit fetch followed by selected local converter |
| Books/notebooks/mail | EPUB, IPYNB, MSG, EML and selected signature/mail types | MarkItDown and selected format-specific parsers |
| Images | Selected JPEG/PNG/BMP/TIFF/WEBP/HEIC/HEIF variants | Maintained codecs plus optional OCR; image metadata alone is incomplete content extraction |
| Audio | Selected WAV/MP3/M4A/FLAC/OGG/OGA/OPUS/WEBM and provider-supported variants | Existing transcription implementation through an explicit adapter |
| Video | MP4 and selected provider-supported video containers | Existing caption/audio transcription paths; no new visual-video pipeline |
| YouTube | Supported video URLs, available captions, language selection and timestamps | Structured transcript library beneath the MarkItDown integration |
| Containers | ZIP members, nested archives, mail attachments and ebook members | Existing parsers behind an owned bounded container manifest |

Evaluation-only libraries are not installed wholesale merely to populate a
catalog. Select the smallest maintained implementation that covers each family.
The exact extension/MIME manifest is a deliverable; new library releases and
third-party plugins do not silently expand the website's advertised support.

For each capability, record: backend/version, dependencies/binaries/assets,
offline/network requirements, required provider modalities, extraction depth,
locator granularity, limits, known omissions and fixture verification state.
Expose clear availability states such as ready, missing dependency/asset,
network disabled, missing provider and upstream unavailable. Recognition alone
does not satisfy the content-support milestone.

## Routing and result contract

Keep the measured native PDFium/pypdf route, current Office adapters,
Markdownify/Pandoc and ordinary OCR where they earn their place. Add selected
MarkItDown converters for the wider catalog behind private adapters. Public
consumers use mdaddict's result contract rather than configuring a competing
converter framework themselves.

Retain the original source and its digest, converter/version/settings identity,
Markdown, located blocks, issues and artifacts necessary to inspect the result.
Use only the location precision the converter actually supplies: document,
page, sheet, cell, archive member or timestamp. Coarse delegated output must not
be assigned invented page boxes or semantic confidence. Source-retention storage
and notebook/version ownership remain application responsibilities.

Record whether the requested content was extracted, partially extracted or
unavailable. Do not label an image's EXIF, a video's description, or a metadata-only
audio result as a complete conversion. Keep unsupported/failed archive members
in the manifest, including their paths, hashes and individual outcomes.

The existing AI provider boundary remains explicit and provider-neutral. Extend
its versioned request/capability contract for audio/video evidence when needed,
preserving current image-provider compatibility. A vision-only provider must
not silently receive an unsupported audio/video request. Local versus remote
inference is an adapter choice; selection, budgets, patch validation and cache
identity stay under mdaddict's workflow.

## YouTube and media

MarkItDown supports YouTube transcript retrieval through its optional
`youtube-transcription` extra. Its current converter delegates to
`youtube-transcript-api`, then joins the caption text and may return metadata
without a transcript. The lower-level library supplies segment start/duration,
language and generated/manual-caption metadata. Use that structured result
when timestamp citations are needed; retain the response and label translations
explicitly. Missing or blocked captions must produce a clear content outcome.

YouTube is an explicit online acquisition feature. Cached caption artifacts can
be processed offline afterwards. Upstream captions are the retained evidence;
successful retrieval does not certify them against the spoken audio or slides.
Hosted retrieval must be tested from the actual deployment environment because
the upstream library documents cloud-IP blocking. Uploaded caption/transcript
files provide a useful explicit alternative when retrieval is unavailable.

The user selected pragmatic video scope: existing captions and audio-track
transcription through maintained adapters, with timestamps when the adapter
provides them. Do not build frame sampling, slide extraction, equation recovery
or whole-video visual understanding for v1. Record those unprocessed visual
modalities explicitly. If a backend returns only a whole transcript, retain
document/video-level attribution rather than inventing segment timings.
Missing captions may use a configured transcription adapter; absent configuration
or upstream unavailability must remain a clear content outcome, not metadata-only
success. Audio-track transcription is the v1 coverage promise.

MarkItDown's built-in audio helper currently calls Google Speech Recognition
without a caller-supplied AI client. Therefore, do not use its unrestricted
default dispatcher as the offline media route. Supply an explicit local or remote
transcription adapter. Pre-provision required assets; model installation must
not occur as a hidden side effect of source conversion. Source-level network
permission and inference-provider permission are separate settings.

## Bounded work before moving the site's main effort onward

1. Freeze the capability manifest and normalized ingestion/evidence contract.
   This lets the rest of the site develop against one stable interface while
   delegated format coverage is implemented.
2. Add the broad-format bridge and explicit acquisition/media adapters. Reuse
   existing conversion APIs; preserve native routes that tested better. Implement
   bounded member count, recursion depth and expanded bytes for containers.
3. Complete job limits, deadlines/cancellation and retained-source review wiring.
   Offline workers deny network access; online/media jobs use explicit policy
   and dependencies. Preserve failures and partial results through restart.
4. Run a format acceptance matrix: representative positive content and meaningful
   omission/failure cases per family, disabled-network/dependency/provider cases,
   timestamp/member/source mapping, source immutability and cache invalidation.
   Every advertised capability needs a supported, configured route and evidence;
   an unavailable optional provider must not be disguised as successful output.
5. Demonstrate upload/import -> source review/correction -> wiki -> practice on
   representative course material. Hold unresolved equations/tables and record
   the correction cost. The current 33 strict equation failures remain a fidelity
   track; this boundary does not certify automatic mathematics.

After the contract is frozen, build the remaining site in parallel with these
adapters. Once the acceptance matrix and source-to-wiki loop pass, shift the
main effort to compilation, wiki usability, practice and private-user operation.
Resume converter research for concrete blocked inputs or measured regressions.

Public PyPI release remains a separate licensing/distribution/release gate.
Publication, commits, cloud uploads and live provider calls remain separate
actions; the local implementation receipt describes what has actually changed.

## Primary evidence

- [Matched converter benchmark](converter-head-to-head-2026-10-26.md)
- [Website/API trial](website-pipeline-2026-10-26.md)
- [MarkItDown formats and extras](https://github.com/microsoft/markitdown)
- [YouTube converter](https://github.com/microsoft/markitdown/blob/main/packages/markitdown/src/markitdown/converters/_youtube_converter.py)
- [Structured transcript API](https://github.com/jdepoix/youtube-transcript-api)
- [Audio transcription helper](https://github.com/microsoft/markitdown/blob/main/packages/markitdown/src/markitdown/converters/_transcribe_audio.py)
- [Archive converter](https://github.com/microsoft/markitdown/blob/main/packages/markitdown/src/markitdown/converters/_zip_converter.py)
- [Unstructured input registry](https://github.com/Unstructured-IO/unstructured/blob/main/unstructured/file_utils/model.py)
