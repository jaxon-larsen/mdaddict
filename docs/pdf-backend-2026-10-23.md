# PDF backend switch — 2026-10-23

Implements the [PDF bake-off](pdf-bakeoff-2026-10-23.md) decision.

The subsequent [existing-corpus comparison](pdf-corpus-2026-10-23.md) covers 29
reviewed pages from 16 PDFs and records the remaining math/table gap. The small
ordinary control results below do not establish a complete fidelity replacement.

## Change

| Item | Choice |
|---|---|
| Default `[pdf]` extra | `pypdfium2` + `pypdf` + `Pillow` (permissive) |
| Optional hard-case stack | `mdaddict[pdf-pymupdf]` (PyMuPDF / PyMuPDF4LLM) |
| `[all]` | PDFium plus Office/HTML/images; excludes the optional PyMuPDF stack |
| `ExtractOptions.pdf_backend` | `auto` \| `pdfium` \| `pymupdf` |
| `auto` resolution | pdfium if it is the only stack; if both extras are installed, keep PyMuPDF until the caller sets `pdfium` |
| Forms | pypdf-only inspector (no PyMuPDF catalog probe) |
| Engine revision | `mdaddict-7` (cache identity includes `pdf_backend` and source implementation) |

CLI: `--pdf-backend auto|pdfium|pymupdf`.

## Original switch verification

- mdaddict package tests: 49 passed, 2 skipped.
- Manual: ordinary multi-column order and form-valid `Specimen 42` succeed with
  `pdf_backend="pdfium"`.

These original counts did not establish PDFium parity: the package suite used
the retained PyMuPDF backend, and the ordinary controls did not cover fractions.

## Review hardening

The PDFium path now holds recognized math, vector paths, nested content and
failed page-object inspection with source-linked unresolved issues. Source text
is retained. This is a conservative capability guard, not a new geometry/table
recognizer: decorative vectors may also be held, and text-only relationships
can still escape detection. The tests include an independently authored stacked
fraction, superscript notation, a vector grid, cached holds and inspection failure.
OCR render dimensions now share the existing 2,400-pixel longest-side ceiling.

PDF AI repair remains implemented only for PyMuPDF. A provider with PDFium
raises `MissingDependencyError` with instructions to explicitly select
`pdf_backend='pymupdf'` and install `[pdf-pymupdf]`, or omit the provider to
retain offline PDFium. No implicit backend selection or model call occurs.

The education app explicitly depends on `mdaddict[all,pdf-pymupdf]` for its
existing math behavior. The public `[all]` install is now permissive-only.
`auto` still prefers an already-installed PyMuPDF stack during the transition;
explicit backend selection is reproducible across mixed environments.

The bake-off table check now reuses the existing structural comparator: it
checks cell boundaries, row/column order, empty cells, multiplicity and spans.
Equivalent HTML/GFM tables pass. Cell-word presence alone cannot pass. Native
extraction holds are reported separately from content-check results.

The original bake-off page slicing also discarded the canonical form tree from
its single-page form control. The harness now uses the original single-page
source unchanged, and pypdf's document-aware page import for multi-page sources.
A regression checks that fields, widget state and appearance diagnostics are
unchanged by preparing that control. Older form results must not be read as
evidence about canonical-field fidelity.

The corrected seven-case PDFium probe has six passing content cases without
holds. The simple table remains a structural mismatch with a source-linked hold.
This is a bounded synthetic result, not general source-fidelity certification.
Raw results: `education/engine/out/pdf-bakeoff/hardened/mdaddict-pdfium.json`.

## Verification after hardening

Windows, Python 3.13.7 and 3.12.13. Pandoc 3.10 was available for combined and
full package checks. No models were downloaded or called.

| Check | Observed result |
|---|---|
| Package source tests with explicit PDFium controls | 58 passed, 1 skipped |
| Fresh installed `[all]`, PyMuPDF absent | 57 passed, 2 skipped |
| Installed wheel tests on Python 3.12, both PDF stacks | 58 passed, 1 skipped |
| Installed package + engine + API tests | 763 passed, 5 skipped, 30 subtests passed |
| Clean `[pdf]`, PyMuPDF absent | 41 passed, 18 skipped |
| Clean `[pdf-pymupdf]` | 34 passed, 18 skipped |
| Clean core + dependency-free smoke | 32 passed, 20 skipped |
| Clean Office / HTML / images extras | 38 / 42 / 33 passed, respectively |
| Build wheel from source distribution; strict Twine metadata check | Passed |
| Installed imports, runtime/resource bytes and dependency consistency | Passed |

The permissive-only `[all]` check explicitly asserts that neither `pymupdf` nor
`pymupdf4llm` is installed. Its two skips are the legacy PDF snapshot and local
OCR. The new PDFium tests execute instead of hiding behind legacy availability.
Other profile skips reflect absent unrelated extras/external tools. The strict
`check_distribution.py --extra all` gate still requires Tesseract and was not
run locally; the direct installed `[all]` suite records its OCR skip explicitly.
Linux/macOS and Docker verification remain pending.

Final wheel: 108,409 bytes, SHA-256
`ff5839f89ff2dc46fadece00caa4b2ca2a5713abaf2900dc950f89ee09ff6d37`.
Source distribution: 193,034 bytes, SHA-256
`fdfa7e0363fc172d2414f753c0f2174dcc2d251c553ea74a9aec8b78de1e5185`.
The wheel's runtime/resource bytes match source. The application wheel explicitly
depends on `[all,pdf-pymupdf]`. Files remain unstaged and uncommitted; no release
workflow or publication was run. Project licensing and dependency review remain
release gates.
