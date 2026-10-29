# Numbered PDF column ordering — 2026-10-23

## Result and scope

The compatibility PDF path now places a qualification below two numbered columns
after both sets of steps. The ordinary-PDF control's complete-content check
passes without changing its gold, adding a dependency, or rewriting its text.
This is a correction for simple native numbered text regions, not general
reading-order or semantic-fidelity certification.

## Feedback loop and root cause

The independently authored control has steps 1–3 in the left column, steps 4–6
in the right column, and a lower qualification. Previously, Markdown placed the
qualification between steps 3 and 4. The step-only order check passed; the
complete-content check correctly rejected the displaced qualification.

From the package root, using an interpreter with the compatibility extra:

```powershell
python -m pytest tests/test_pdf_order.py -k qualification_follows -q
```

That regression failed before the change and passes afterward. The copied
invented PDF's provenance/hash is in `tests/fixtures/README.md`; no private
research paper or textbook is included in the distribution.

Three hypotheses were ranked before probing:

1. Upstream column grouping absorbs the lower note into the left column:
   confirmed. Raw `pymupdf4llm==0.0.27` output already has the defect, and its
   column rectangles combine the heading/left steps/lower note before the right
   steps. Its rectangle-joining logic permits the vertically distant note to
   remain in that left-column region.
2. mdaddict's recovery code changes the order: contradicted by raw output.
3. Header detection or conversion options cause the split: disabling headers,
   enabling glyph extraction, or setting 24-point margins independently leaves
   the defect. No parser upgrade or model-backed layout path was enabled.

## Reused implementation

The existing PowerPoint numbered-region planner now lives in `reading_order.py`,
with `pptx_order.py` retained as a compatibility import. The planner function's AST
is identical to the previous wheel's implementation. Existing PPTX behavior and
legacy application imports remain covered by their tests.

The PDF adapter supplies native text regions to that shared planner only for
parallel numbered content. It requires numbering and disjoint column geometry
to agree. Regions above the sequence precede it; regions below it follow it.
Conflicts, rotation, overlaps, more than two columns, or intervening regions
cannot justify a permutation.

Before moving anything, require a unique mapping of **every** native text
region to **every** Markdown paragraph. Heading/emphasis presentation can be
ignored for matching, but literal native emphasis/underscore characters cannot
be discarded. Reorder complete original Markdown chunks; keep their text,
formatting, punctuation, Unicode and separator inventory. The page block is
constructed afterward, so source offsets describe the final output.

Pages containing drawings, images, links, annotations or forms are left to their
existing extraction paths and guards. Unnumbered and non-parallel layouts are
also outside this correction. Structured Markdown or ambiguous paragraph
ownership on an attempted correction retains the original output with a
page-linked `pdf_reading_order_unresolved` hold. The shared review policy keeps
that code blocking even if legacy severity is informational. A successful
permutation records an informational `pdf_reading_order_recovery`; it does not
mark the content human-reviewed.

## Corpus verification

A fresh paired run reuses the 16 originals, 29 reviewed pages, 18 jobs per backend
and unchanged imported gold from the [corpus comparison](pdf-corpus-2026-10-23.md).
Compared with the [decimal-guard run](numeric-guard-2026-10-23.md), only the intended
compatibility page's Markdown and coverage verdict change. That page preserves
its complete character inventory. All other reviewed outputs/verdicts match.

| Result | PDFium | Compatibility |
|---|---:|---:|
| Content matches | 26/54 | 44/54 |
| Held reviewed pages | 22/29 | 16/29 |
| Unheld pages with known content mismatches | 0 | 0 |
| Stable cache replays | 18/18 | 18/18 |

No new ordering holds appear in this corpus. Decimal holds and their actual
publication probes remain intact. These are selected difficult cases; zero
unheld mismatches among these checks does not establish zero errors elsewhere.
The remaining mismatches and pending visual/code/circuit acceptance are not
cleared by this result. No OCR or AI requests were made.

Private evidence remains under `education/engine/out/reading-order-2026-10-23/`:
the option probes, fresh backend reports, `comparison.json`, `distribution.json`,
the reproduction script, installed-wheel environment, and combined-suite JUnit
report. Original/source/gold hashes are checked before and after extraction.
Earlier raw corpus reports remain unchanged.

## Regression and distribution checks

The focused PDF-order, existing PPTX-order and application review-policy set
passes **26 tests**. It covers the real control and cache replay, unowned/duplicate
paragraphs, conflicting numbering, rotations, interrupted/third columns,
literal-underscore loss, Unicode/format preservation, source insertion order,
and blocking legacy acceptance while independent pages remain eligible.

Fresh installed-wheel checks on Windows Python 3.13.7 pass:

| Profile | Passed | Skipped |
|---|---:|---:|
| Core, including dependency-free CLI/import smoke | 52 | 23 |
| PDF, with PyMuPDF absent | 61 | 21 |
| Compatibility PDF | 57 | 18 |
| Office | 58 | 17 |

Skips in isolated profiles reflect absent unrelated extras and external tools.
The combined installed-wheel package/engine/API run passes **791 tests and 30
subtests**, with **5 skips**, in 204.84 seconds. It uses the existing API dependency
versions and a fresh Python 3.13.7 environment containing this wheel with both
PDF stacks and native extras. From the application root:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = 'engine/src;api/src;engine;api/tests;engine/tests/extract'
$env:PATH = 'C:/Program Files/RStudio/resources/app/bin/quarto/bin/tools;' + $env:PATH
engine/out/reading-order-2026-10-23/integration/Scripts/python.exe -m pytest engine/tests api/tests ../mdaddict/tests --import-mode=importlib --junitxml=engine/out/reading-order-2026-10-23/junit.xml -q
```

Use your installed Pandoc location. Linux/macOS, local OCR quality and
release/license gates remain separate. Reproduce the corpus using the retained
`engine/out/reading-order-2026-10-23/run.py` with the application's interpreter.

Build from source distribution and strict Twine checks pass. Wheel runtime/resource
bytes and the source distribution's regression fixture/tests match current source.
Artifacts in `out/reading-order/dist/`:

- Wheel: 110,910 bytes, SHA-256
  `78558cc5bba1ae9e64ade141458a4f657e42bf207529ceec4ffdd9adc048f2ba`.
- Source distribution: 198,865 bytes, SHA-256
  `9bf0db09bbb5f0b7de0fd8221a0ac7fc81b41ee7bd5aef54f79843bae41a50dd`.

No debug instrumentation or new parser/provider dependency was added. Changes
remain local and uncommitted; nothing was published.
