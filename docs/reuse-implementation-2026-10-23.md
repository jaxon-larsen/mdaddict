# mdaddict reuse implementation — 2026-10-23

The later [PDF backend work](pdf-backend-2026-10-23.md) changes the default PDF
extra and adds review hardening. This receipt's parser/dependency decisions,
counts and artifact hashes below describe the earlier HTML/OMML delivery.

## Implemented decision

Reuse established conversion code while retaining mdaddict's public API, source
locations, issue contract, cache validation and optional repair workflow.
The user explicitly favors copying bounded components where useful. No model
downloads, model evaluation, provider calls, commits, pushes or publication were
performed in this implementation.

| Component | Integration | Reason |
|---|---|---|
| Ordinary HTML | `markdownify==1.2.3`, optional `html` extra, included in `all` | Its maintained API already performs HTML rendering. Copying it would still require Beautiful Soup and maintaining a fork. |
| PowerPoint Office equations | Copy only `omml2latex==0.1.1`'s `_parser.py` | A 65,542-byte self-contained stdlib component; the CLI and document loader are unnecessary. Supported equations no longer need a temporary DOCX or Pandoc process. |
| Complex HTML and unsupported Office equations | Retain existing Pandoc fallback | Avoid known flattening/formatting regressions while preserving existing capabilities. |
| DOCX, PPTX structure/order, XLSX | Retain Pandoc, python-pptx and openpyxl integrations | The comparison did not establish a better complete replacement for required behavior. |
| PDF | No backend replacement in this batch | Text-only candidate probes do not establish layout, math, table, form or source-mapping parity. The current PyMuPDF stack still needs a permissive-default decision before release. |

The base install still declares no runtime dependencies. Imports remain lazy;
HTML image references are never fetched, and AI still requires an explicit
developer-supplied adapter. The CLI remains offline.

## Copied component and compatibility

The copied parser is byte-identical to the verified upstream release. Its full
Apache 2.0 license, copyright attribution, archive/file hashes and update
instructions ship under [`src/mdaddict/_vendor`](../src/mdaddict/_vendor/README.md)
in both the wheel and source distribution. The release wheel had no upstream
NOTICE. `.gitattributes` preserves the parser/license bytes across checkouts.
mdaddict's project license remains undecided.

Local handling lives separately in `office_math.py`: reject unsupported content
before the parser can silently discard it, preserve literal TeX punctuation,
move a source-proven trailing NBSP outside the closing math delimiter, and
remove redundant braces around single script bases. The source XML is copied
before adjustment. Unsupported equations use the retained Pandoc bridge when
available, otherwise source-linked unresolved issues still hold their blocks.
The adapter preserves shape/paragraph placement and repeated occurrences.

HTML uses Markdownify's existing heading, table, list and text machinery.
MathML/TeX, merged/nested tables, embedded objects, backtick-bearing preformatted
code and code pipes in table cells retain the existing Pandoc path. Literal
Markdown punctuation is escaped, scripts/styles/head metadata are omitted,
and image alt text goes through mdaddict's established unresolved-marker path.
Installing the HTML extra is optional; existing Pandoc-only HTML installations
still work. Complex HTML continues to require Pandoc.

Cache identity now includes Markdownify/Beautiful Soup versions and recursively
fingerprints Python sources, including the copied parser. The original seven
packaging snapshots remain unchanged. Their parity test permits only two
reviewed TeX whitespace changes in `algebra.pptx`, with exact corresponding
offset shifts; every other character, source locator, issue and status matches.

## Verification

Windows, Python 3.13.7 and 3.12.13; Pandoc 3.10 for full document tests.

| Check | Observed result |
|---|---|
| Package suite, Python 3.13 | 50 passed, 1 skipped |
| Installed package suite, Python 3.12 | 50 passed, 1 skipped |
| Installed mdaddict + engine + API suite, Python 3.13 | 747 passed, 5 skipped, 30 subtests passed |
| Clean core wheel + dependency-free smoke | 32 passed, 19 skipped |
| Clean `html` wheel | 42 passed, 9 skipped |
| Clean `office` wheel, without Pandoc on PATH | 38 passed, 13 skipped; supported PPTX equations still execute |
| Clean `pdf` wheel | 34 passed, 17 skipped |
| Clean `images` wheel | 33 passed, 18 skipped |
| Wheel built from sdist; strict Twine metadata checks | Passed |
| Shipped parser/license hashes and runtime/resource bytes | Match source; vendor notices included in both artifacts |
| Installed application dependency check and import paths | Passed; mdaddict, engine and API load from installed packages |

Extra-specific skips reflect absent unrelated format dependencies and external
tools. The combined installed suite covers all Python extras and Pandoc. Local
Tesseract is unavailable, so the strict `--extra all` integration gate (which
requires Tesseract) was not run. Linux/macOS CI and Docker checks were not run.
Passing these regressions does not establish complete source fidelity.

The final README refresh changes distribution metadata only; runtime/resource
bytes match the tested installed wheel. Final wheel: 104,875 bytes, SHA-256
`187ccd338d10b63e2e7f5ca82ae5928e1ee122d3b06f6b64806319a9070f2d33`.
Final sdist: 188,134 bytes, SHA-256
`775c7c8555aad3ab258410a5df841cb6aa929ea6af349a52effe1df79c5363ce`.

## Bounded performance and content check

The existing offline reuse worker was rerun against the same 12 hash-bound
synthetic inputs, using one initial conversion and five warm repetitions. It
blocks Python socket connections and checks deterministic repeated output.
These are full mdaddict conversion times, including contract/cache identity
work, rather than raw library timings. They are separate runs on this host,
not a controlled general performance benchmark.

| Input | Before, warm median | After, warm median |
|---|---:|---:|
| Basic HTML | 38.65 ms | 4.16 ms |
| Repeated HTML paragraphs | 43.61 ms | 4.10 ms |
| Simple HTML table | 31.80 ms | 3.98 ms |
| Algebra PowerPoint | 73.93 ms | 21.93 ms |

All previously passing synthetic whole-document checks still pass, including
merged HTML tables and MathML through the fallback. Both full algebra documents
retain known mismatches, including pictured content; no overall accuracy gain
is claimed. Fixture-specific native equation/source-span tests pass separately.
Raw output is retained under ignored
`out/reuse-evaluation/implemented-mdaddict.json`; original comparison results
remain in `out/reuse-evaluation/final/report.json`.

## Remaining gates

Evaluate existing permissive PDF primitives against layout/table/math/form and
source-mapping controls before changing the default. Keep model-based evaluation
deferred until requested. Settle the project license and run external-tool,
cross-platform and container gates before release. Files remain local,
unstaged and uncommitted.
