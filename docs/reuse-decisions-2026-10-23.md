# Reuse decisions — 2026-10-23

The subsequent [PDF backend receipt](pdf-backend-2026-10-23.md) records the PDFium
default and review hardening. PDF shortlist/open-decision statements below
describe the original reuse evaluation; the target plan owns the current direction.

## Decision

Reuse established parsers and converters. Retain mdaddict's API, source mapping,
issues, cache validation, and optional repair orchestration. The user subsequently
authorized implementation and favors bounded copying when useful: ordinary HTML
now uses optional Markdownify, and PowerPoint equations use a vendored
`omml2latex` parser with separate compatibility handling. See the
[implementation receipt](reuse-implementation-2026-10-23.md). The comparative
measurements below describe the original evaluation, before those changes.

User constraints confirmed during this evaluation:

- Default backends should prioritize permissive dependencies suitable for
  proprietary/commercial consumers without buying a separate dependency license.
- Model downloads and model-based evaluation are deferred. This task evaluates
  code and library reuse, not model quality.
- Files remain local, unstaged, and uncommitted.

The best near-term reuse opportunities are **Markdownify for ordinary HTML** and
**an existing OMML-to-LaTeX package for PowerPoint equations**. The PDF stack
needs a permissive replacement evaluation before release; a text-only probe
cannot establish parity with current layout/math behavior.

## Component decisions

| Area | Install/use | Copy/vendor | Decision and boundary |
|---|---|---|---|
| Ordinary HTML | `markdownify==1.2.3` in the optional `html` extra | No | Implemented through its public API. Keep Pandoc for math, merged/nested tables and code cases that Markdownify misrenders. No new general HTML renderer. |
| Office equation XML | No additional installed library | Copy `omml2latex==0.1.1` parser only | Implemented after user authorization: 65,542-byte stdlib-only component, unchanged upstream bytes, full Apache 2.0 license and provenance. Native equations avoid Pandoc; unsupported structures retain its fallback or unresolved issues. DOCX still uses Pandoc. |
| DOCX document structure | Existing Pandoc executable plus our anchoring adapter | No full MarkItDown/Docling Word backend | Keep the current path for now. Plain Pandoc omits the fixture's Title paragraph; our wrapper preserves it. Mammoth and Docling retain ordinary fixture text, but full algebra controls still expose differences. |
| PPTX | Existing `python-pptx`, our thin source/order adapter | No full competitor converter | Keep the adapter. MarkItDown and native Docling both emit the numbered-column control in 1,3,2,4 order. Docling does recover native equations, so its OMML subcomponent is worth isolating. |
| XLSX | Existing `openpyxl` | No | Keep the small existing wrapper. MarkItDown emits `NaN` for the formula expression; native Docling emits an empty formula cell and drops the sheet heading in this control. No need to add pandas for our current behavior. |
| PDF text, rendering and fields | Shortlist `pypdf`, `pypdfium2`; evaluate `pdfplumber` for its existing layout/table APIs | No full MarkItDown PDF converter yet | Install existing primitives; avoid writing new PDF readers/renderers/table detectors. These text-only candidates pass the two-page prose control. Tables, math, geometry, OCR integration and issue/source mapping remain unverified replacements. |
| Pandoc Python wrapper | Keep the current direct subprocess call | No | Do not add `pypandoc` without a concrete discovery/bundling requirement. It uses the same Pandoc engine; this probe measures additional wrapper overhead without better conversion. |
| MarkItDown as the base engine | No default dependency | No whole-project fork | A useful comparison/reference, but its tested broad profile is larger and changes required behavior. Underlying small libraries are the better integration seam for now. |
| Docling as the base engine | No default dependency in this phase | Narrow OMML candidate only | Its native Office path is useful evidence, but the selected installation is comparatively large and still changes required order/formula behavior. Models are explicitly deferred. |
| mdaddict contracts, diagnostics and repair | Keep | Not applicable | These express our product behavior. Competitor parsers do not directly replace the full contract. Avoid conflating this glue with reimplementing a parser. |

These integrations do not establish complete release acceptance or general fidelity.
Current formats and source controls remain gates; the PDF decision is still open.

## Measured synthetic probe

Windows, Python 3.13.7, Pandoc 3.10. Twelve synthetic documents: six existing
hash-bound Office/PDF controls, five small HTML cases and one XLSX formula case.
The benchmark reuses the application's existing `benchmark_content` evaluator
and independently authored gold. No real-source corpus, OCR/VLM model evaluation,
or external AI calls were used. MarkItDown's bundled ONNX file-type classifier
is part of its ordinary execution and dependency footprint.

Each worker blocks Python socket connections, captures raw output, runs one first
conversion plus five warm repetitions, and checks repeated output consistency.
Whole-document checks cover content, order, repetition, table structure and math;
they do not establish source-location parity. Pagination comments and equivalent
GFM inline-math fences are presentation-normalized only for scoring.

| Observation | Result |
|---|---|
| Markdownify on three ordinary HTML controls | All three match; 0.29–0.48 ms warm conversion |
| Current mdaddict on the same controls | All three match; 31.80–43.61 ms warm conversion |
| Merged HTML table and MathML | Current path matches both; Markdownify, MarkItDown and native Docling mismatch both |
| Held-out DOCX text/repetition, two separate files | mdaddict, Mammoth/Markdownify, MarkItDown, python-docx text and native Docling match both; direct Pandoc drops the Title paragraph |
| Numbered-column PPTX control | mdaddict matches; MarkItDown and native Docling reorder the steps |
| XLSX formula control | mdaddict retains `=A2*2`; MarkItDown yields `NaN`; native Docling yields an empty cell |
| Two-page PDF prose control | mdaddict, MarkItDown, PDFium text, pypdf text and pdfplumber text match |
| Full algebra DOCX/PPTX controls | No evaluated complete-document path matches all expected content; pictured equations and other structural differences remain |

The last row is important: no overall winner or general accuracy percentage is
claimed. The PDFium/pypdf/pdfplumber entries are parser-only probes, not equivalent
Markdown converters. Native Docling preserves the tested Word and PowerPoint
fractions/radicals; MarkItDown preserves the tested DOCX equations but loses
their PPTX counterparts. Complete-unit mismatches should not hide those strengths.

Import times vary considerably between first and later runs; they are retained
in raw results but are not used to rank packages. Warm times describe these tiny
fixtures on this machine. Process-tree RSS was sampled approximately every 10 ms
and is exploratory. The Pandoc wrapper and direct path used the same 3.10 binary;
wrapper HTML medians were 101–139 ms, versus 32–44 ms for the current direct path.

## Dependency weight

Metadata-listed installed files, excluding Python, bytecode caches, external
Pandoc/Tesseract binaries and model data. Counts include each requirement's
transitive closure in this environment. They are not download sizes or marginal
costs when dependencies are shared. Editable mdaddict metadata excludes its source
tree, so the approximately 75.7 KB built wheel is the useful core size reference.

| Requirement/profile | Distributions | Installed-file MiB |
|---|---:|---:|
| `markdownify==1.2.3` | 5 | 0.84 |
| `omml2latex==0.1.1` | 1 | 0.14 |
| `mammoth==1.13.0` | 2 | 0.23 |
| `pypandoc==1.17` (binary excluded) | 1 | 0.11 |
| `python-docx==1.2.0` | 3 | 10.19 |
| `pypdf==6.10.0` | 1 | 1.37 |
| `pypdfium2==5.14.0` (bundled PDFium included) | 1 | 7.66 |
| `pdfplumber==0.11.10` | 8 | 41.64 |
| Pre-integration `mdaddict[all]` | 11 | 75.34 |
| `markitdown==0.1.9` base | 19 | 113.90 |
| `markitdown[docx,pptx,xlsx,pdf]` | 36 | 204.78 |
| `docling-slim[format-office,format-html,convert-core,cli]==2.142.1` | 54 | 236.75 |

The current mdaddict profile still includes PyMuPDF and has not met the newly
confirmed default licensing requirement. No default PDF migration was performed.

## Copying versus installing

Static local-import closures in installed MarkItDown 0.1.9 are approximately:

| Entry converter | Local modules | Source lines, including comments |
|---|---:|---:|
| HTML | 4 | 425 |
| DOCX | 11 | 1,777 |
| PPTX | 8 | 940 |
| PDF | 4 | 808 |

These are syntactic closures, not a proven minimal extraction. They still need
their external libraries. Copying the DOCX converter therefore does not remove
Mammoth, Markdownify, XML handling or their update/security work. Copying
Markdownify itself also retains the Beautiful Soup dependency. Installing its
maintained public API is the better default choice.

One bounded vendoring candidate was found: Docling's `omml.py` and `latex_dict.py`,
about 34 KB of source, with lxml and pylatexenc dependencies. Both files declare
MIT headers and name their DWML ancestry; upstream DWML declares Apache 2.0.
Any extraction needs complete provenance and license/notice review across that
chain. Do not infer clearance solely from a top-level repository license.

The alternative `omml2latex` package is about 144 KB installed, declares Apache
2.0 and has no third-party runtime dependencies. It and Docling's OMML converter
match all six basic controls: fraction, square root, super/subscripts, combined
scripts and a 2×2 matrix. Redundant braces around the single base `x` were
explicitly reviewed as equivalent spellings. This is not full Office-math
certification. The older `dwml==0.3` candidate errors on a fraction lacking
optional `fPr`, despite matching the other five controls; it is not preferred.

Following the user's explicit preference for bounded copying, vendor only
`omml2latex/_parser.py` from the verified 0.1.1 release. This removes its unrelated
CLI/document loader and adds no runtime dependencies. Keep the 65,542-byte parser
unchanged, its 11,358-byte Apache license and attribution, and record release/file
hashes. The small mdaddict wrapper adds validation and compatibility; it does not
implement equation conversion. This supersedes the initial dependency-first
recommendation. Do not copy a whole competitor backend or build another parser.

Sources: [Markdownify](https://github.com/matthewwithanm/python-markdownify),
[MarkItDown](https://github.com/microsoft/markitdown),
[Docling OMML](https://github.com/docling-project/docling/blob/main/docling/backend/docx/latex/omml.py),
[DWML license](https://github.com/xiilei/dwml/blob/master/LICENSE),
[omml2latex](https://pypi.org/project/omml2latex/),
[PDFium integration/licensing](https://pypdfium2.readthedocs.io/en/stable/readme.html#licensing),
and [PyMuPDF licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).
Source metadata and installed versions were inspected on 2026-10-23. This is an
engineering shortlist and notice/provenance review, not a legal compatibility opinion.

## Reproduction and retained evidence

The tooling is in `tools/evaluate_reuse.py`, `tools/evaluate_omml_reuse.py` and
`tools/reuse_inventory.py`. Its reference-root argument points at the application
checkout only to reuse authored controls and existing scoring code; production
mdaddict does not depend on that checkout. From the application root:

```powershell
uv venv --python 3.13 ../mdaddict/out/reuse-evaluation/venv
uv pip install --python ../mdaddict/out/reuse-evaluation/venv/Scripts/python.exe 'markdownify==1.2.3' 'markitdown[docx,pptx,xlsx,pdf]==0.1.9' 'python-docx==1.2.0' 'pypandoc==1.17' 'pypdfium2==5.14.0' 'pypdf==6.10.0' psutil 'docling-slim[format-office,format-html,convert-core,cli]==2.142.1' 'dwml==0.3' 'omml2latex==0.1.1'
$env:PATH = 'C:\Program Files\RStudio\resources\app\bin\quarto\bin\tools;' + $env:PATH
../mdaddict/out/reuse-evaluation/venv/Scripts/python.exe ../mdaddict/tools/evaluate_reuse.py --reference-root . --out ../mdaddict/out/reuse-evaluation/final --baseline-python ../mdaddict/.venv/Scripts/python.exe --repeat 5
../mdaddict/out/reuse-evaluation/venv/Scripts/python.exe ../mdaddict/tools/evaluate_omml_reuse.py --reference-root . --out ../mdaddict/out/reuse-evaluation/omml.json
```

The baseline interpreter must already have editable mdaddict with its native
extras installed. Use your own Pandoc location; the example reflects this host.
Raw outputs, timing logs, hash-bound cases, inventories and OMML controls remain
under ignored `out/reuse-evaluation/`. The earlier `run/` directory contains a
superseded pilot with an incorrect DOCX gold mapping and a PDFium API mistake;
only `final/report.json` and the final `omml.json` support the results above.

## Implementation status after this evaluation

1. Implemented the ordinary-HTML adapter through Markdownify's public API, preserving
   complex-table/math behavior and the zero-dependency base install.
2. Implemented the bounded OMML copy with Office-math/source-span controls;
   retain the temporary-DOCX/Pandoc route only for unsupported structures.
3. Evaluate permissive PDF engines against existing layout/table/math/form and
   source-mapping controls before selecting the new default. Reuse their native
   APIs; do not build another PDF parser or table-recognition engine.
4. Keep existing direct Pandoc, python-pptx, openpyxl and pypdf integrations where
   they already provide the required behavior. Defer model-based comparisons.
