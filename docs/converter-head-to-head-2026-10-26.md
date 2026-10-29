# mdaddict converter head-to-head — 2026-10-26

This follow-up directly measures MarkItDown and Unstructured against mdaddict
on the frozen PDF corpus. It addresses the missing competitor comparison in
the earlier [website pipeline trial](website-pipeline-2026-10-26.md). These
results compare conversion output and runtime; no competing tool was assigned
a fabricated source-review or publication contract.

## Matched comparison

Each profile ran serially in its own Linux container with four CPU quota,
8 GiB memory and no network during document processing. Python 3.12.13 and the
same base image/system OCR tools were used. MarkItDown 0.1.9 and Unstructured
0.27.34 / inference 1.6.14 are pinned published releases. Unstructured uses
CPU Torch 2.10.0, torchvision 0.25.0 and provisioned local model assets.

| Profile | Completed | Strict shared checks | Sum of adapter time | Median adapter time | Peak cgroup memory | Empty exports |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mdaddict native, installed | 100/100 | 39/85 | 19.9s | 0.147s | 0.13 GiB | 0 |
| MarkItDown offline | 100/100 | 22/85 | 60.5s | 0.582s | 0.10 GiB | 8 |
| Unstructured fast | 100/100 | 33/85 | 23.5s | 0.195s | 0.48 GiB | 9 |
| Unstructured auto | 100/100 | 33/85 | 45.4s | 0.276s | 0.73 GiB | 1 |
| Unstructured ocr_only | 100/100 | 35/85 | 391.5s | 3.724s | 0.71 GiB | 1 |
| Unstructured hi_res | 100/100 | 37/85 | 1160.9s | 11.193s | 1.57 GiB | 1 |

Adapter time covers conversion and supported Markdown export, including the
small evaluation-side page/raw metadata preparation. Initialization, source-byte
verification, IPC and evidence writes are recorded separately in the JSON
receipt. These single-pass totals/medians are not stable service SLO estimates.
The original native source-mounted run is retained as a diagnostic. The primary
native result uses a freshly built/installed wheel because reading implementation
files over a Windows bind mount disadvantaged it against Linux-installed peers.
The wheel passes build/strict Twine checks and its 28 Python modules match the
current source byte-for-byte. Native installed/source output equality is audited.

## What the scores cover

There are 100 target cases and 101 processed pages; one form preserves an extra
unscored page. The unchanged gold supplies **85 shared automatic checks**,
19 manual checks and six mdaddict-specific quarantine checks. Quarantine checks
are N/A in this content comparison. Six additional real pages have narrow
source-reviewed gold, 54 additional real pages are throughput-only, and none
has exhaustive full-page gold. Scores are named-check matches, not general
page-accuracy percentages. Per-kind and per-cohort counts are in the receipt.

The neutral scorer keeps raw exports. It accepts pipe, LaTeX and HTML table
representations as cell grids, preserving blanks and checking declared row/column
spans. Nine independent blank/span/sign/representation/negation controls verify
that normalization. Text/order checks read visible words inside table cells,
without Markdown/HTML delimiters; this post-output correction is recorded and
applied uniformly (MarkItDown gains one match). No gold changes. Other strict
math/full-unit checks remain unchanged;
math-format mismatches may still require semantic source inspection. No plain
OCR string was wrapped into math to manufacture a pass. The inherited form uses
page metadata where available; MarkItDown's full-document export has no such
page mapping, which is recorded explicitly.

MarkItDown has 15 strict text mismatches; ten retain the expected character
sequence if whitespace is ignored. Unstructured fast/auto each have three such
text mismatches, all present under that diagnostic. These are formatting evidence,
not independent semantic passes. The scores must not be read as counts of lost
facts or complete-page accuracy.

MarkItDown's primary converter recovered the ordinary grid, genuinely empty-cell
control and decimal-cell control. It also concatenated words in parts of the
real quantum textbook, reordered selected numbered content, omitted selected
form values, and produced spurious table structure on a reviewed page header.
Those observations support targeted component reuse rather than a wholesale
replacement. The 33 structured equation targets remain a major limitation of
the native/text-OCR paths; a fast text export alone does not recover their scope.

Unstructured uses its public `elements_to_md` exporter and retains ordered raw
elements plus table HTML. The fast and auto runs each match 33 checks; explicit
OCR-only matches 35. Auto selected fast on 91 inputs and OCR-only on nine. The
explicit fast profile selected fast for all 100. The layout/table profile is
37/85, matches all 28 text targets, and recovers none of the 12 strict table/matrix
targets. A table-shaped
HTML export only passes when values, positions and declared spans match gold.

## Footprint and operating implications

Logical installed Python files total 45.9 MB for native PDF dependencies,
253.3 MB for MarkItDown's PDF environment, and
2298.5 MB for the full Unstructured PDF environment.
These counts retain common pip/psutil and package metadata, including the installed
mdaddict wheel in the native environment. System tools, Docker layers
and external weights are separate. Unstructured's extra model/cache assets are
332.1 MB. The declared PDF extra brings the model dependency closure
even when only `fast` is selected; a hand-minimized fast-only installation was
not measured. YOLOX's hosted checkpoint has no model card, so checkpoint license
clearance remains incomplete; this evaluation does not approve redistribution.

Cold assets were prepared before timing. spaCy en_core_web_sm 3.8.0 must be
preinstalled for this Unstructured release; its tokenizer otherwise attempts a
download. HF offline settings, telemetry opt-outs and Docker network isolation
were used. Requested and actual routing are retained per input, with warnings,
timeouts/errors and unrun cases kept in the denominator. The setup transfer delay
is recorded separately from conversion quality and latency.

The earlier website report's summary was corrected during this audit:
**26/54 prior native content checks and 4/6 quarantine sentinels**, rather than
24/54 and 6/6. The two quarantine mismatches require particular issue codes;
those pages still have blocking issues. Sources, gold and raw results did not
change. The current neutral comparison excludes all six policy checks.

## Decision and next step

Keep mdaddict's source/evidence/repair shell and permissive native defaults.
MarkItDown supplies useful table-conversion evidence, but its measured broad PDF
behavior does not justify replacing the current path wholesale. Evaluate a
bounded delegation of those table operations through maintained APIs, preserving
form inspection, source mapping and honest uncertainty. The full Unstructured
stack's added footprint must earn its place through recovered content, rather
than category labels alone. Fully automatic mathematical fidelity remains open.

This is the first matched PDF lane. Current PyMuPDF, GPU-oriented full-page OCR
and larger real Office panels remain separate comparisons. Competitor web/API
integration has not been benchmarked here; the earlier mdaddict API/recovery
measurements remain their own receipt. No production converter, default or
dependency was changed, and nothing was committed or published.

Primary API sources: [MarkItDown](https://github.com/microsoft/markitdown),
[Unstructured partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning),
[Unstructured Markdown exporter](https://github.com/Unstructured-IO/unstructured/blob/0.27.34/unstructured/staging/base.py),
[Table Transformer](https://huggingface.co/microsoft/table-transformer-structure-recognition)
and [YOLOX checkpoint](https://huggingface.co/unstructuredio/yolo_x_layout).
The [public-safe aggregate](converter-head-to-head-2026-10-26.summary.json)
contains counts, measurements and hashes. Private source outputs, code, complete
inventories and preparation logs remain under the education checkout's ignored
`engine/out/head-to-head-2026-10-26/` directory. A public checkout alone cannot
reproduce the private-source corpus.
