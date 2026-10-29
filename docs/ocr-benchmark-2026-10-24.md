# mdaddict local OCR and parsing benchmark — 2026-10-24

Finalized 2026-10-26 from the saved 2026-10-24 measurements. Finalization verifies
the saved evidence and does not rerun model inference.

## Decision

Keep mdaddict's lightweight native conversion and source/review contract. This
trial supports reusing optional specialist backends, rather than replacing the
package with one universal parser or writing OCR algorithms ourselves.

The small formula recognizers are useful candidates for a fast local path.
PP-FormulaNet Plus-S and Plus-M preserve five of six inspected equation crops;
RapidLaTeXOCR and pix2tex preserve four. GraniteDocling 258M and LightOnOCR-2-1B
preserve all six inspected crops, at substantially higher CPU latency. These
are source-inspected outputs, not population accuracy or independently blinded
human scores. Keep uncertain math held; neither a model's confidence nor a
passing crop establishes that its surrounding page or diagram is correct.

MinerU standard merits further testing as a complete optional parser. On the
shared panel it matches 10/15 PDF checks and 5/8 lecture checks; the saved native
PDFium reference matches 6/15 and compatibility matches 11/15 PDF checks. Native and raster input modes
are distinct. MinerU still changes a Boolean operand and omits pictured math. Its
license has additional conditions, so it does not meet the project's preference
for an unrestricted permissive default. No production dependency, backend,
source span, review hold, core size, or default model behavior changed.

## Protocol and limits

Windows x64, Core Ultra 5 125H (14 cores/18 threads), 32 GB RAM, Intel integrated
graphics, no NVIDIA GPU. Isolated Python 3.12 environments use Torch CPU
2.10.0/torchvision 0.25.0 for conventional engines and Torch CPU
2.14.1/torchvision 0.29.1 for compact models. Transformers is 5.20.2. Each engine
uses four CPU threads where configurable. Initial exploration overlaps model
families; its latency ranges are indicative, not a controlled speed ranking.
The serial warm measurements below separate reusable runtime throughput from
cold model import/load. These are Python CPU profiles, not optimized GPU,
OpenVINO, or quantization comparisons for every model.

Reuse the existing 29 reviewed PDF pages from 16 originals: 17 real pages and
12 authored controls, with 54 automatic content checks (21 math, four tables,
two matrices, and 27 text/order/coverage checks). Render once at 150 DPI using
PDFium. OCR engines receive identical PNGs; LiteParse's scan profile receives
a lossless image-only PDF wrapper. Docling and LiteParse native profiles also
receive the prepared original PDF page/text layer. These input modes are
deliberately distinguished. Visible appearance cannot recover a hidden stored
form value, and a native parser has information that raster OCR does not.
All 31 image objects decoded from the wrapper exactly preserve the source RGB
pixels; a Poppler-rendered lecture page was also visually checked.

Two additional lecture image cases have eight content checks. Slide 6's input
places all its original pictures at their source slide locations, retaining
all three formulas; slide 13 uses its original exercise picture. Six separate
formula crops use existing math gold and pre-result visually selected regions.
One is the original reviewed 300 DPI Boolean crop; five are recorded crop boxes
from the fixed images, upscaled 2x. Crop coordinates/gold are never sent as
answers to a recognizer. Crops test recognition, not automatic region discovery.

The fixed smoke panel has nine PDF pages and both lecture-image cases. Slow
profiles use explicitly smaller shared subsets; their denominators are shown.
Warm/cold runs, setup failures and timeouts are retained. Conventional per-case
limits are 120s, document pipelines 300s; compact models have a cold 120s crop
or 300s page limit and 6 GiB tree-RSS cap. These resource limits, FP32/BF16
choices, reference attention kernels and incomplete coverage can change the
ranking. A timeout is unavailable quality evidence, not a wrong transcription.

Package pins: LiteParse 2.17.0, RapidOCR 3.10.0, EasyOCR 1.7.2, docTR 1.1.0,
Docling-slim 2.142.1, PaddleOCR 3.7.0/PaddlePaddle 3.3.1, MinerU 4.0.12,
RapidLaTeXOCR 0.0.9, pix2tex 0.1.4, and ONNX Runtime 1.31.0. The portable
Tesseract baseline is 5.5.3.20260724 with the existing English fast data.
RapidLaTeXOCR 0.0.9 declares Python <3.13; this Python 3.12 trial does not
establish support across mdaddict's full Python version range.

The existing gold and comparators are unchanged. Official DocTags decoding,
generation terminator removal, and formula-task TeX fence/delimiter decoding
are adapter operations; raw outputs remain available. Separate reviewed
equivalents handle redundant grouping and source punctuation. They do not
silently change automatic verdicts. The strict table comparator does not parse
HTML tables, and Demsar's expected numeric subtable is narrower than some
valid full-table outputs. Do not read these sentinel counts as whole-page
accuracy. There is no broad degraded-scan, handwriting or multilingual test.

Quarantine/publication adapters and diagram topology remain untested/manual.
No raw candidate's output clears mdaddict's existing holds. There were no
cloud OCR requests, private-document uploads, commits, pushes or publication.
Python network guards cover Python transports, not native socket auditing;
all inference configurations point to local assets and local runtimes.

## Page and image results

Pass/checked counts below exclude execution errors; unavailable checks are
shown separately. A partial profile's denominator is only its selected checks.
The 2026-10-23 native reference remains PDFium 26/54 and compatibility 44/54
after the numbered-column fix; those are historical reference runs, not fresh
OCR measurements. See [reading-order evidence](reading-order-2026-10-23.md).

| Profile | PDF input mode | PDF inputs attempted | PDF content checks | Lecture inputs attempted; checks |
|---|---|---:|---:|---:|
| Docling standard | native PDF | 29/29 | 24/54 | 2/2; 3/8 |
| Docling + CodeFormulaV2 | native PDF | 3/29 | 2/2; 3 unavailable | 1/2; 3/5 |
| docTR ResNet50/CRNN | raster/image | 9/29 | 4/15 | 2/2; 4/8 |
| docTR MobileNet | raster/image | 9/29 | 4/15 | 2/2; 3/8 |
| EasyOCR English | raster/image | 9/29 | 2/15 | 2/2; 1/8 |
| LiteParse OCR, native PDF | native PDF | 29/29 | 25/54 | 2/2; 2/8 |
| LiteParse OCR, raster PDF | raster/image | 29/29 | 11/54 | 2/2; 2/8 |
| RapidOCR PP-OCRv6 small | raster/image | 29/29 | 18/54 | 2/2; 4/8 |
| Tesseract PSM 3 | raster/image | 29/29 | 19/54 | 2/2; 4/8 |
| Tesseract PSM 6 | raster/image | 29/29 | 16/54 | 2/2; 4/8 |
| GraniteDocling 258M | raster/image | 0/29 | — | 2/2; 5/8 |
| LightOnOCR-2-1B | raster/image | 1/29 | unavailable (2 checks) | 1/2; 5/5 |
| MinerU basic ONNX | raster/image | 29/29 | 22/54 | 2/2; 5/8 |
| MinerU standard llama.cpp | raster/image | 9/29 | 10/15 | 2/2; 5/8 |
| PaddleOCR v6, oneDNN disabled | raster/image | 5/29 | 0/8 | 1/2; 4/5 |
| PaddleOCR v6, oneDNN setup failure | raster/image | 3/29 | unavailable (4 checks) | 0/2; — |
| PP-StructureV3, oneDNN disabled | raster/image | 2/29 | 0/4 | 1/2; 5/5 |

Tesseract and RapidOCR recover the lecture exercise's wording/order but fail
all four lecture equation targets. Plain OCR preserves useful characters
without necessarily preserving math structure, cell relationships or columns.
EasyOCR/docTR do not justify replacing those paths on the small shared panel.
Docling's formula-enriched dense Wong and Nielsen pages exceed 300s; its
completed lecture exercise still drops the equation and scrambles list order.
PP-Structure's simple-table output fills an empty result cell with “Pass”; its
column order also fails. These are meaning errors, beyond the HTML comparator's
format limitation. MinerU standard's Wong page 50 adds an incorrect complement
to A in the third Boolean product while correctly recovering the truth table.
The same equation is correct in its dedicated Plus-M crop recognizer. Successful
blocks do not certify their surrounding page. The general parsers warrant
source-specific evaluation.

## Formula crops

The reviewed-equivalent column is a named Codex source/gold/output inspection,
not an automatic relaxation or human validation. Completed/attempted includes
resource-capped cases. Exploration times exclude model load for completed
cases; peak sampled RSS includes cold workers. GB is decimal.

| Recognizer | Completed/attempted | Strict checks | Reviewed equivalents | Inference range | Peak RSS |
|---|---:|---:|---:|---:|---:|
| GLM-OCR | 1/2 | 0/1; 1 unavailable | 1/1 | 75.28–75.28s | 2.63 GB |
| GraniteDocling 258M | 6/6 | 2/6 | 6/6 | 44.68–88.28s | 1.94 GB |
| LightOnOCR-2-1B | 6/6 | 5/6 | 6/6 | 20.66–46.59s | 4.51 GB |
| LightOnOCR-3-0.8B | 0/2 | unavailable (2 checks) | no complete output reviewed | cold process cap 120s | 4.00 GB |
| PaddleOCR-VL-1.6 | 0/2 | unavailable (2 checks) | no complete output reviewed | cold process cap 120s | 4.10 GB |
| pix2tex / LaTeX-OCR | 6/6 | 2/6 | 4/6 | 0.73–1.92s | 0.63 GB |
| RapidLaTeXOCR ONNX | 6/6 | 1/6 | 4/6 | 0.47–1.36s | 0.30 GB |
| PP-FormulaNet Plus-M, ONNX | 6/6 | 3/6 | 5/6 | 1.77–2.42s | 0.86 GB |
| PP-FormulaNet Plus-S, Paddle | 6/6 | 3/6 | 5/6 | 2.40–9.10s | 0.83 GB |

The distinguishing failures are substantive: RapidLaTeXOCR/pix2tex lose Boolean
overbars and complement scope. Both, plus PP-FormulaNet S/M, turn dotted
background marks in the phase-state picture into mathematical dots, subscripts
or an extra matrix. GraniteDocling and LightOnOCR-2 preserve that equation.
GraniteDocling's complete Bloch-picture input produces picture tags rather
than transcribing the pictured formulas; its correct equation crops do not
establish automatic picture interpretation. LightOnOCR-2 passes the exercise
image but exceeds 300s on the small full-page table. GLM-OCR returns an
equivalent Nielsen formula and times out on the phase crop. LightOnOCR-3-0.8B
and PaddleOCR-VL-1.6 return no result for their two 120s crop probes here.
LightOnOCR-3 logs reference fallbacks for causal-convolution/delta-rule kernels.
These findings apply to the tested CPU configurations, not their GPU quality.

Model artifacts, excluding the runtime: RapidLaTeXOCR ~179 MB, pix2tex ~122 MB,
PP-FormulaNet Plus-S ~257 MB, Plus-M ONNX ~591 MB, GraniteDocling ~515 MB,
LightOnOCR-2 ~2.01 GB, LightOnOCR-3 ~1.71 GB, PaddleOCR-VL ~1.89 GB, and GLM-OCR
~2.65 GB. Tokenizer/config files add overhead. Torch/Paddle/ONNX and dependency
closures are additional; the combined evaluation environment is not a minimal
installation-size measurement. The stdlib-only mdaddict core is unchanged.

## Serial warm formula timing

One unscored warmup, then two runs of each fixed crop, one engine at a time.
Other benchmark inference workers are stopped during this phase. Load time
and warmup are recorded separately; six stable pairs do not establish broad
determinism. The full raw exploratory timing receipts are also retained.
Plus-S's approximately 36s cold import/load here matters for short-lived
processes; a warm 2.09s/crop median is not total file-conversion latency.

| Engine | Median | Range | Stable pairs | Import/model load |
|---|---:|---:|---:|---:|
| plus-m | 3.042s | 2.797–3.737s | 6/6 | 17.14s |
| plus-s | 2.092s | 1.972–2.769s | 6/6 | 36.07s |
| rapid | 2.302s | 1.755–3.244s | 6/6 | 6.97s |

## Reuse and licensing

Use maintained APIs and optional dependencies first. Copy a bounded component
only with provenance, dependency closure, license/notice review, and measured
benefit. A repository's public source alone is not permission to copy its
weights or ignore additional terms.

- [GraniteDocling](https://huggingface.co/ibm-granite/granite-docling-258M) and
  [LightOnOCR-2](https://huggingface.co/lightonai/LightOnOCR-2-1B) publish Apache-2.0
  model licenses. [LightOnOCR-3](https://huggingface.co/lightonai/LightOnOCR-3-0.8B)
  is a distinct Qwen3.5 model, not interchangeable with version 2.
- [PaddleOCR-VL-1.6](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) is
  Apache-2.0; its direct Transformers example is element recognition, not the
  complete page parser. The PP-FormulaNet Plus-S model card is Apache-2.0.
  Plus-M's ONNX bundle retains original-model terms. The measured adapter uses
  installed MinerU code, whose additional conditions still matter; it is not
  automatically a permissive vendoring candidate.
- [MinerU's license](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)
  adds commercial thresholds and online-service attribution to Apache-2.0.
  Local evaluation fits its stated grant, but broad package consumers may face
  different obligations. Treat optional use separately from a permissive default.
- [Surya's modified model license](https://raw.githubusercontent.com/datalab-to/surya/master/MODEL_LICENSE)
  has a competitor restriction. Surya/Marker weights were excluded rather than
  downloaded for this competing converter. Texify's
  [GPL-3.0 code](https://github.com/VikParuchuri/texify/blob/master/LICENSE) and
  [deprecated status](https://github.com/VikParuchuri/texify) do not fit the
  preferred default path.
- RapidLaTeXOCR/pix2tex use MIT project code, but separate weight-license
  confirmation remains necessary. Release downloads stalled; pinned HF mirrors
  were used, with exact local SHA-256 and mirror provenance. Similar published
  file sizes are not independent proof of upstream byte identity.
- [LiteParse](https://github.com/run-llama/liteparse) is the LlamaIndex-related
  local option actually tested, including its bundled Tesseract. LlamaParse's
  paid hosted service was not used. olmOCR and DeepSeek's documented GPU paths,
  UniMERNet's older dependency stack, and additional large OCR models were
  researched but not run in this bounded Windows CPU evaluation.

## Setup corrections, provenance and reproduction

RapidLaTeXOCR omits `requests`; it was installed after an approved retry.
Paddle 3.3.1's oneDNN path raises an unsupported PIR attribute error here;
the approved alternate CPU path works. PP-Structure needed an additional
lazily loaded textline-orientation model. Its Markdown key is `markdown_texts`;
an initial harness used the wrong key and was rerun, never treated as model
quality. MinerU standard's CPU override must preserve the Engine class type;
an initial wrapper error was corrected after approval. Each old attempt is
retained separately. The final pipeline/compact harness stops on the first
upstream exception, before repeating the same setup error on other inputs.

Private evidence stays in the education checkout's ignored
`engine/out/ocr-benchmark-2026-10-23/` directory (preparation date). It contains
the fixed plan, images/lossless scan wrapper, raw outputs, model provenance,
initial failed attempts, process/time/RSS receipts, unchanged-source/model/code
hash audit, crop decisions, and `scored.json`. No source excerpts or model files
were added to this public package's tracked files.
An [aggregate JSON receipt](ocr-benchmark-2026-10-24.summary.json) contains the
cohort counts and warm timing statistics without source excerpts or local paths.

`prepare.py`, `add_crops.py`, and `scan_pdf.py` record preparation. `worker.py`
and `control.py` run conventional adapters; `pipelines/run_pipelines.py` runs
Paddle/MinerU; `compact/run.py` runs fixed crop/page probes. `score.py`,
`review_crops.py`, `audit.py`, `warm_math.py` and `make_report.py` retain scoring,
review decisions, provenance and report generation. Individual package versions
and model revisions/hashes are in their receipts. Source documents are private,
so a public checkout alone cannot reproduce this source-bound trial.

Next: validate the shortlisted specialists on more independent held-out math,
tables and degraded scans; measure uncertainty routing and false acceptance;
then integrate one explicit optional backend through mdaddict's existing
provider/review boundary. Preserve the native fast path and default offline
behavior. This trial does not authorize silently downloading models for users,
automatically accepting generated formulas, or replacing all format adapters.
For the permissive path, prefer Paddle's maintained API before considering a
bounded copy; the measured MinerU ONNX wrapper's additional terms require a
separate reuse decision. Evaluate the runtime/dependency closure as well as the
model file size before choosing an extra. The related S/M models share the
observed phase-state failure; agreement between them would not detect it.

Follow-up: the [Linux website pipeline trial](website-pipeline-2026-10-26.md)
now measures automatic discovery, additional source checks, API caching/load
and process recovery. Its narrow gold and local-container limits remain explicit.
