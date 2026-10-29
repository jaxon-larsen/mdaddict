# PDF corpus comparison — 2026-10-23

## Decision

Retain the application's explicit PyMuPDF compatibility stack. The permissive
PDFium path is useful for text extraction with unresolved holds; the existing
source-backed controls do not support treating it as a complete replacement for
structured equations, matrices or tables.

The next bounded reuse experiment should target table relationships using
maintained extraction APIs and these exact failing cases. Structured equation
recovery is the larger remaining capability decision. Keep it separate from
table formatting or broader format expansion; no models were evaluated here.

Follow-up: [LiteParse with OCR disabled](liteparse-evaluation-2026-10-23.md) uses
these same prepared inputs and content checks. It recovers the simple table but
does not justify a default-backend change or broad source-code port.

After the [decimal preservation guard](numeric-guard-2026-10-23.md), a fresh run
retains all Markdown and content verdicts while compatibility holds increase
from 15 to 16 pages. Counts below describe the original pre-guard snapshot.

The subsequent [numbered-column correction](reading-order-2026-10-23.md) improves
compatibility to 44/54 content matches with the same 16 holds. No selected content
mismatch remains unheld; this does not certify whole-page or general fidelity.

## Corpus and method

- 16 existing PDFs: three textbooks, three research papers and ten invented
  ordinary/held-out/form controls.
- 29 distinct source pages: 17 real-source pages and 12 control pages.
- Existing gold only, selected from `suite.json`, `textbook-gaps.json`,
  `research-sentinels.json`, `quantum-offline.json`, `ordinary-pdf.json`,
  `heldout.json`, and `forms.json` in the education benchmark fixtures.
- Repeated source-hash/page pairs use the first existing case in that manifest
  order; later manifests add only previously uncovered pages. Expected passages,
  equations and accepted renderings were not changed.
- 77 existing checks: 54 automatic content checks, six quarantine sentinels and
  17 pending visual/code/circuit reviews. Content counts below exclude quarantine
  and manual review.

This is an intentionally difficult, selected sample, not an estimate of general
PDF accuracy or the population's false-hold rate. Most real-page targets are
named passages/formulas rather than full-page semantic gold. Synthetic controls
are reported separately and must not inflate claims about real documents.

Both backends use the same source hashes and reviewed pages, offline extraction,
OCR off, and a zero AI request budget. Python socket connections are blocked.
No models, external API calls, OCR or production backend changes were involved.
Source PDFs, manifests and imported gold hashes were verified unchanged afterward.

The existing evaluator now accepts `--pdf-backend pdfium|pymupdf|auto`, records
the actual extractor, separates per-case unresolved holds from check outcomes,
and records conversion time separately from benchmark preparation. Form sources
retain their canonical field tree. Non-form PDF subsets use the existing
PyMuPDF-based benchmark preparation on both sides; this run evaluates PDFium
conversion, not a wholly PyMuPDF-free evaluation harness.

## Automatic content results

Counts are matching named checks, not accuracy percentages.

| Check kind | PDFium matches | Compatibility matches |
|---|---:|---:|
| Text passages | 17/17 | 15/17 |
| Reading-order sentinels | 4/4 | 3/4 |
| Complete-unit coverage, mainly synthetic | 5/6 | 5/6 |
| Equations in the required Markdown/LaTeX representation | 0/21 | 15/21 |
| Tables | 0/4 | 3/4 |
| Matrices | 0/2 | 2/2 |
| **All selected automatic content checks** | **26/54** | **43/54** |

PDFium's text matches do not establish equation or cell relationships. Its math
failures mean the expected structured expressions were not matched; they do not
mean every operand vanished. Retained plain glyphs cannot establish two-dimensional
formula meaning. The compatibility backend is also incomplete on this corpus.

| Source group | PDFium content matches | Compatibility content matches |
|---|---:|---:|
| Real sources, 17 pages | 14/40 | 30/40 |
| Invented controls, 12 pages | 12/14 | 13/14 |

PDFium preserves the ordinary multi-column/footer order control that the
compatibility path misorders. The compatibility path reconstructs the ordinary
table grid that PDFium leaves as text. Real research-paper cases expose
remaining table and math failures in both paths.

## Holds, publication checks and cache integrity

| Measure | PDFium | Compatibility |
|---|---:|---:|
| Pages with unresolved holds | 22/29 | 15/29 |
| Real-source pages held | 17/17 | 12/17 |
| Control pages held | 5/12 | 3/12 |
| Pages with a failing selected content check but no hold | 0 | 2 |
| Actual held-page publication probes passing | 22/22 | 15/15 |
| Stable, successful cache replays | 18/18 | 18/18 |

The two compatibility cases without holds are the DART numeric-value sentinel
and the ordinary multi-column complete-content check. The first loses the
required decimal presentation in a reconstructed table cell; the second places
the footer qualification before the last steps. A successful extraction status
does not certify either page.

The original quarantine sentinels report 4/6 passes for PDFium and 6/6 for the
compatibility path, including one unexercised conditional check in each. Two
PDFium sentinel mismatches require the legacy `pdf_glyph_unresolved` issue code;
PDFium instead holds those pages with its layout/math codes. The independent
supplementary probes reuse the application's actual publication validator for
every currently held case and confirm that those actual holds block dependent
claims. No expected codes or original gold were relaxed to obtain a pass.

All 17 original visual/code/circuit checks remain pending. No old visual approval
was transferred to a changed output. Every source job validates the extraction
contract and checks source integrity; all 36 backend/job runs completed with no
blocked sources or extraction/evaluation errors.

## Spot-checking apparent over-holds

Three additional-held pages whose selected content checks pass were inspected
using full-page Poppler renders alongside their outputs:

- The flattened form retains labels and text values but omits selected checkbox
  and radio states in both native outputs. Its passing text sentinel cannot
  establish that the PDFium hold is unnecessary.
- Nielsen PDF page 112 has mathematical exercises, inline equations and operator
  notation beyond its passing prose sentinel.
- DART PDF page 11 has branching algorithm structure and a numeric table beyond
  the passing value/order sentinels; algorithm control flow remains unreviewed.

These checks did not establish any of the three holds as a false positive. This
does not prove the broad vector guard has no false positives. Its operational
cost is clear: every real reviewed page in this hard-case sample is held.

Source/output/render hashes and the diagnostic observations are retained locally
in `review/notes.json`. These observations are not new gold or manual acceptance.
Poppler 26.07.0 at 110 DPI was used. The flattened-control render reported missing
Symbol/ArialUnicode display fonts; that warning is recorded with the inspection.

## Timing and reproducibility

Per-source conversion and replay timings are retained in the raw reports. The
two backend processes ran concurrently, and their first conversions included
cold imports. No controlled throughput claim or speed ranking is made from
these timings. No whole-book performance or OCR/model quality was measured.

Local evidence is under `education/engine/out/pdf-acceptance-2026-10-23/`:

- `plan.json`: unchanged suite/gold fingerprints, exact source selection and
  local source paths.
- `run.py`: generated reproduction script invoking the existing evaluator.
- `pdfium.json`, `pymupdf.json`: per-source/per-case results and cache replays.
- `comparison.json`: content/hold counts, publication probes, evaluator hashes
  and raw-report hashes.
- `review/`: three source-page renders and bound inspection notes.

From the application root, with the existing interpreter containing both stacks:

```powershell
engine/.venv/Scripts/python.exe engine/out/pdf-acceptance-2026-10-23/run.py pdfium
engine/.venv/Scripts/python.exe engine/out/pdf-acceptance-2026-10-23/run.py pymupdf
```

Individual reviewed suites can also use the existing `evaluate_benchmark.py`
CLI with explicit source mappings and `--pdf-backend`. Its normal nonzero exit
for failed/manual gates remains meaningful; a completed corpus run is not a
passing release gate.

The evaluator changes passed 53 focused benchmark/content/review/bake-off tests.
Package runtime behavior and its dependencies were unchanged. Originals,
source-derived Markdown and renders remain local; only aggregate notes were
added to the standalone package repository. Changes remain unstaged and
uncommitted. Public release, licensing, cross-platform/OCR verification and the
remaining fidelity work are still separate gates.
