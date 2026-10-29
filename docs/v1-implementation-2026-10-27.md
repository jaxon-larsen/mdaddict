# mdaddict v1 ingestion implementation — 2026-10-27

The local implementation now exposes the agreed ingestion boundary. This is
format/runtime integration; the earlier equation/layout fidelity failures have
not been repaired or reclassified as passing.

## Implemented boundary

- `extract()` / `to_markdown()` retain their local-file API. `ingest()` adds
  explicit `file`, `url` and `youtube` kinds. URLs require `allow_network=True`.
- The standard-library-only `capabilities()` catalog pins extensions, MIME types,
  reader choice, optional dependencies/tools, network/provider requirements,
  coverage and locator granularity. Availability is distinct from fixture
  verification and from fidelity certification. Unlisted plugins do not expand it.
- Schema 1.0 stays compatible. `metadata.ingestion` summarizes input kind,
  catalog revision, coverage, source hash and actual locator units. Cache identity
  includes new reader/codec versions, tool versions and source implementation.
- Existing native PDF/Office, Markdownify/Pandoc and OCR paths remain. Extended
  readers invoke allowlisted MarkItDown 0.1.9 converter classes, never its default
  dispatcher, implicit speech service, cloud converters or plugins.
- Added local readers: XLS, EPUB, IPYNB, MSG, RSS/Atom, MIME mail/P7S, bounded ZIP,
  SRT/WebVTT, HEIC/HEIF, legacy DOC/PPT through LibreOffice and selected Pandoc
  formats. Wikipedia/Bing snapshots use selected maintained readers.
- Notebook output/attachment omissions, cached XLS values, unenumerated MSG
  attachments, EPUB visual content and legacy layout all retain explicit issues.
  These delegates have document-level provenance, not invented page geometry.
- ZIP/mail share recursive member/depth/expanded-byte budgets. Generated temporary
  filenames prevent member-path writes; manifests retain original paths/hashes,
  child source locators, failed members and rebased Markdown spans.
- URL acquisition bounds bytes/time/redirects, validates public DNS on every hop,
  pins the vetted connection address while retaining TLS host validation, and
  strips sensitive headers across host redirects. Proxies and transport
  compression are not silently enabled. Conversion does not crawl linked assets.
- Remote responses retain exact downloaded bytes/digest/origin, in `.sources`
  or base64 metadata. Caption evidence retains structured API text/times/language
  and generated/manual flags, explicitly not the original video/caption XML.
  Remote evidence uses separate cache keys so origins cannot contaminate a later
  local-file result for identical bytes.
- Existing AI adapters remain image-only by default. Audio requires declared
  `audio` modality and explicit `MediaAttachment`/`TranscriptSegment` records.
  One transcription request has no implicit retries. Video uses bounded ffmpeg
  audio extraction; visuals stay unresolved and untimed responses stay untimed.

## Website integration

The sibling education API has bounded chunked upload reads and queue admission
before persistence, a default 32-job queue and a 900-second deadline measured
from original creation. Extraction runs in a killable process, including through
the synchronous worker entry point. Tests can explicitly inject a direct runner.

Scoped cancellation persists in the job. A shared commit/cancel fence prevents
later publication; a publication that already won the fence stays published.
Late progress/retry updates cannot erase cancellation. Provider calls in the
compiler are checked before/after but still require finite transport timeouts.

The API exposes catalog lookup, cancellation and explicit remote import.
`ALLOW_REMOTE_SOURCES` defaults false. An enabled import retains its request,
then persists the fetched artifact/caption response as the original, verifies
its digest and imports it into the existing review/version/compiler workflow.
Existing configured file-extraction/compiler providers remain independent of
the remote-acquisition setting. The UI continues to use file upload; the new
remote/cancel controls are API features, ready for frontend integration.

## Verification and limits

Local deterministic checks cover source/cache integrity, offline opt-in,
private-address rejection, container budgets and unsupported members, exact
transcript times, provider modality rejection, invalid-response cache refusal,
source retention and a real process termination. Authored positive content
controls exercise notebook/feed/EPUB/subtitles/HEIF, Pandoc readers, and actual
LibreOffice DOC/XLS conversions. Existing native-format and API review tests
are retained. No live providers or public caption services were called.

Fresh verification:

| Check | Result |
| --- | --- |
| Windows Python 3.13 source package suite with Pandoc 3.10 | 107 passed, 1 optional Tesseract skip; one upstream XLS-engine deprecation warning |
| Existing/full API suite plus new ingestion bounds | 101 passed, 2 optional skips |
| API ingestion tests after router separation | 9 passed |
| API ingestion/extraction checks after final source-identity changes | 14 passed |
| Engine extraction/compiler compatibility rerun | 479 passed, 2 optional skips, 27 subtests passed |
| Final Linux Python 3.12 fresh `all` wheel, Pandoc 3.10 and Tesseract | 102 passed, 6 optional skips; verifies no PyMuPDF or HEIF binary codec |
| Fresh Windows core wheel | 63 passed, 38 optional dependency/tool skips; standard-library smoke passed |
| Build sdist/wheel and strict Twine metadata | passed |

The Linux installation verifies PDFium is present and PyMuPDF/HEIF are absent.
Its six skips are the explicit PyMuPDF/HEIF controls and missing LibreOffice
bridge; the actual DOC/XLS bridge is exercised on Windows. The read-only test
mount causes an advisory pytest-cache warning, not a failed check.

Every individual extra also passed in a fresh Windows interpreter:

| Profile | Passed | Optional skips |
| --- | ---: | ---: |
| core | 63 | 38 |
| pdf | 72 | 36 |
| pdf-pymupdf | 68 | 33 |
| office | 69 | 32 |
| images | 64 | 37 |
| html | 73 | 28 |
| extended | 77 | 24 |
| captions | 65 | 36 |
| heif (explicit opt-in) | 65 | 36 |
| online | 63 | 38 |

The individual-profile snapshot wheel was 136,622 bytes, SHA-256
`1de7ba600fd4d40f6b6e16b8db604a46aa825c1a0b138df353310bf0356693d2`.
The final default-extra exclusion changes metadata/README only; runtime source
is identical. Final `all` and `online` reruns use the 136,746-byte wheel,
SHA-256 `e36bf84f465b2b059f9e69ebc90026da5f29ae08baacb36b9ac079ee57d43cf7`.
An initial matrix run mixed edited tests with an older wheel; those failures
were discarded and the matrix was frozen. One parallel online check encountered
pytest collection in a disappearing shared temporary directory; explicit
`--rootdir`/`--confcutdir` boundaries fix the harness, and the online rerun passes.
No setup/harness failure is counted as a content failure or successful check.

Remaining acceptance work:

- Positive binary MSG, detached/signed-mail variants and the full image/video
  codec inventory need representative acceptance fixtures. `acceptance_pending`
  rows remain visible. Models and live transcription quality were not evaluated.
- Captions may be unavailable or blocked on hosting-provider IPs. No live hosted
  YouTube claim follows from deterministic adapter tests.
- Process isolation is not an OS network sandbox. Provision binaries/assets,
  denied egress for offline workers and a permitted acquisition lane before
  deploying untrusted legacy documents. No hosting/deployment was performed.
- The queue/fence implementation targets one API process. Distributed durable
  exclusive claims, parser memory/CPU isolation, and crash/redeployment acceptance
  remain necessary before multi-instance operation.
- Audio/video require a developer-supplied audio provider. The website's existing
  image adapters are not automatically reinterpreted as speech adapters.
- Build/package checks and structural fixtures do not certify mathematical
  fidelity, source completeness, licensing clearance or public-release readiness.

## Reuse and dependencies

The new glue uses public maintained parser APIs or selected pinned converter
classes; it does not copy whole frameworks. No additional source was vendored.
The `extended` extra carries MarkItDown's transitive dependencies, including its
detector/runtime imports; consumers needing only native formats need not install
it. `captions`, `heif` and `online` are separate extras. `all` includes local
readers, excludes online caption dependencies, PyMuPDF and the HEIF binary
codec, and does not configure a model or download tools.

The version bounds prevent Pandas 4 removing the selected XLS engine.
The installed `pillow-heif` 1.8.1 bundled-library notice states that its binary
wheels are GPLv2 because they include x265. The wrapper's BSD metadata alone
does not describe the wheel. Therefore `heif` stays explicit and is excluded
from `all`; a decoder-only build/dependency decision remains before enabling
HEIF by default for the website.
Final project/dependency/model/binary license clearance remains a release task.
The existing vendored OMML parser is unchanged.

Primary references: [MarkItDown 0.1.9](https://github.com/microsoft/markitdown),
[pysubs2](https://pypi.org/project/pysubs2/),
[pillow-heif](https://pypi.org/project/pillow-heif/),
[HEIF wheel license notice](https://github.com/bigcat88/pillow_heif/blob/master/LICENSES_bundled.txt),
[Pandoc readers and sandbox](https://pandoc.org/MANUAL.html),
[structured transcript API](https://github.com/jdepoix/youtube-transcript-api).
