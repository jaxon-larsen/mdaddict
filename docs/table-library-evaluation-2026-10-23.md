# Dedicated table APIs — 2026-10-23

## Decision

Do not add a default table dependency or port a competitor's table pipeline yet.
The measured deterministic APIs recover the ordinary ruled control, but do not
close the existing textbook table/matrix gaps under whole-page discovery.
pdfplumber's line mode is the smaller candidate for a future optional ruled-table
adapter. Camelot's network mode helps with borderless tables, but its footprint
and prose false detections do not justify adopting it for the current default.

Keep the existing PDFium/compatibility choices and unresolved holds. More parser
comparisons are not a substitute for fixing demonstrated publication-safety
defects or completing the source-to-wiki flow. Model-based OCR remains deferred.

## Method

Windows x64, Python 3.13.7, isolated `pdfplumber==0.11.10` and `camelot-py==2.0.0`.
Shared PDFium/Pillow versions match the prior corpus environment. No ML/OCR extra,
Torch, Transformers, model weights, hosted parsing or AI calls were used.

Five fixed profiles: pdfplumber's default line strategy and its documented
text/text strategy; Camelot's default lattice, stream and network parsers.
Lattice explicitly uses PDFium without backend fallback. No per-source column
separators, threshold tuning, expected rows, or annotated regions are supplied
to the primary conversion pass.

Reuse the exact prepared files from the [29-page corpus](pdf-corpus-2026-10-23.md)
and [LiteParse run](liteparse-evaluation-2026-10-23.md): 16 originals, 18 jobs,
29 reviewed pages. The extra unreviewed inherited-form page is not requested.
All original/manifest/imported-gold/input hashes remain unchanged. The six
existing targets are four tables and two matrices. Native grids receive the
same cell normalization and exact-grid comparison as the existing checker;
they are not interpreted as a complete Markdown conversion or a hold adapter.

Before candidate parsing, author five additional control pages independently:
ruled and borderless grids with an empty cell, a recorded zero and repeated rows;
a header with one colspan and one rowspan; aligned instructional prose; ordinary
prose. The last two require zero discovered tables. Positives require exactly one
table, exact cells/multiplicity, and the merged control additionally requires
native geometry/borders to preserve both spans. The five-page PDF was rendered
with Poppler at 80 DPI and all five images inspected before parsing. Generic
missing Symbol/ArialUnicode display-font warnings occurred; the Helvetica
controls rendered legibly without clipped content. These are invented controls,
not a representative real-source accuracy corpus.

## Results

| Fixed profile | Existing table/matrix targets | New positive controls | New no-table controls |
|---|---:|---:|---:|
| pdfplumber lines | 1/6 | 2/3 | 2/2 |
| pdfplumber text | 0/6 | 0/3 | 0/2 |
| Camelot lattice | 1/6 | 2/3 | 2/2 |
| Camelot stream | 0/6 | 0/3 | 0/2 |
| Camelot network | 0/6 | 2/3 | 1/2 |

The two line-based successes cover the ruled empty/repetition grid and merged
header; neither finds the borderless control. Network matches the ruled and
borderless grids, misses the merged header, and turns the aligned prose into a
table. Text/stream profiles include surrounding page content in their grids and
also classify both no-table controls as tables. No post-result cleanup removes
blank rows, headings, footnotes, or repeated content to manufacture a pass.

Both whole-page target matches are the existing ordinary simple table. The
four numeric-grid relationships and two mathematical matrix representations
must be distinguished: a general table API is not a formula recognizer. A strict
grid mismatch can also reject a larger table containing the requested subgrid,
as already noted for Demsar in the LiteParse receipt. Counts do not imply every
cell's text was lost. Whole-page detections outside reviewed targets have no
complete gold and are not labeled true/false positives.

A separate **location-assisted diagnostic** supplied the three existing Wong
bounding boxes to each API, with no expected cells or new separators. None of
the fifteen region/profile combinations matches its target. Typical stream
results still merge `A B C` or four adjacent matrix entries into one cell.
These annotated regions are not generally available to callers; their results
are not mixed into automatic-discovery counts. No further case-specific tuning
was attempted.

All 95 profile/job repeats were stable after canonical serialization. Each
profile parsed 34 reviewed/control pages twice, totaling 340 page passes. There
were no execution failures. Content mismatches are reported, not treated as
passing quality gates. Publication/hold behavior, whole-page prose fidelity,
production source spans, cache integration and model-enabled OCR are unmeasured.

## Dependency and reuse implications

Recorded installed mandatory closures in the evaluation environment total
43,539,757 bytes across eight distributions for pdfplumber and 235,862,026 bytes
across fifteen for Camelot. These are logical installed files, excluding generated
bytecode and Python; shared dependencies overlap with existing extras, so the
totals are not incremental install costs. Metadata and versions are retained.
Neither total is a clean cross-platform distribution or complete native-license
clearance. The projects declare MIT licensing; bundled/transitive components
still need normal release review before production adoption.

pdfplumber's public API already provides located cells, rows and spans through
rectangular cell geometry. Its table module is about 650 lines but imports shared
geometry/text utilities and consumes its PDFMiner-backed page abstraction.
Copying it does not automatically remove that input/dependency contract. Do not
build a second PDF geometry reader simply to reproduce this API. Use the
maintained package if a future integration earns its added size and semantics;
copy only a demonstrably useful, separable component with provenance and notices.

Primary API references: [pdfplumber table settings](https://github.com/jsvine/pdfplumber#table-extraction-settings),
[Camelot parser methods](https://github.com/camelot-dev/camelot/blob/master/docs/user/how-it-works.rst).
Observed calls use the pinned installed releases, rather than assuming current
documentation proves behavior on this corpus.

## Evidence and reproduction

Private artifacts are under `education/engine/out/table-libraries-2026-10-23/`:
`prepared.json`, fixed authored `control-gold.json`, `controls.pdf` and its five
rendered pages, five raw profile reports, `comparison.json`, `regions.json`,
`inventory.json`, and the scripts. Real-source grids stay local. No production
package dependency or runtime behavior changed as part of this evaluation.

From the application root, with the retained controls and prior corpus present:

```powershell
uv venv --python engine/.venv/Scripts/python.exe engine/out/table-libraries-2026-10-23/.venv
uv pip install --python engine/out/table-libraries-2026-10-23/.venv/Scripts/python.exe --only-binary :all: pdfplumber==0.11.10 camelot-py==2.0.0 pypdfium2==5.14.0 Pillow==12.3.0
engine/.venv/Scripts/python.exe -X utf8 engine/out/table-libraries-2026-10-23/run.py
engine/out/table-libraries-2026-10-23/.venv/Scripts/python.exe -X utf8 engine/out/table-libraries-2026-10-23/regions.py
```

Python sockets were disabled during conversion; this is not an OS-level network
barrier. Only local input files and deterministic parser modes were used.
