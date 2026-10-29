# mdaddict website pipeline evaluation — 2026-10-26

The later [matched converter comparison](converter-head-to-head-2026-10-26.md)
adds MarkItDown, Unstructured and an installed-wheel native baseline. This report
retains its own source-mounted API/proposal measurements; timings across the
two harnesses are not a code-optimization comparison.

Keep the native PDFium/Tesseract path as the default. Paddle's layout and
PP-FormulaNet Plus-S APIs are practical CPU options for **optional, held formula
proposals**, but this trial does not support automatically accepting their output.
The immediate website work is bounded job execution and an explicit repair
adapter, rather than adding another general parser or making models mandatory.

## Measured Linux behavior

Docker Desktop Linux on the existing Windows Core Ultra 5 125H host, capped at
four CPUs and 8 GiB, with networking disabled during inference. These are local
container measurements, not hosted service latency or browser-side execution.

| Serial extraction, 100 cases | Native | Native + layout/Plus-S proposals, v1 |
| --- | ---: | ---: |
| Completed / execution errors | 100 / 0 | 100 / 0 |
| Total extraction phase | 29.24s | 366.68s |
| Per-case median / p95 | 0.26 / 0.56s | 2.84 / 7.57s |
| Peak cgroup memory, including file cache | 0.13 GiB | 1.10 GiB |
| Review holds | 90/100 | 90/100 |

The first model document took 17.37s, including
reported model initialization of 6.76s. Subsequent
routed documents had a 3.18s median.
The v1 batch made 85 layout calls, returned 447 proposals, and deferred 130 more
regions at the explicit 12-proposal document cap. Twenty-seven routed pages had
no formula detection; this includes tables/figures and is not a measured formula
miss rate. No OOM events occurred. Summed process-tree RSS peaked at 1.36 GiB;
it double-counts some shared pages and differs from cgroup memory accounting.

Timing includes the first model load and extraction/cache writes, excludes image
build, container startup and corpus preparation. The evaluation image is 2.90 GB
uncompressed, with roughly 394 MB of layout/formula assets mounted separately.
It is an evaluation environment, not an optimized production image or the base
mdaddict installation. Python 3.12.13, Paddle 3.3.1, PaddleOCR 3.7.0, PaddleX
3.7.2, PDFium 5.14.0 and Tesseract 5.5.0 were recorded; full versions, model/code
hashes, image digest and resource limits are retained. oneDNN was disabled.
Cross-OS timing is not a controlled speed comparison with the earlier Windows run.

## Accuracy and coverage limits

The frozen corpus contains 17 known real calibration pages, 12 known synthetic
pages, 60 additional real pages from six existing sources, and 11 new authored
controls. Six additional real pages have source-reviewed **narrow** gold; the
other 54 are throughput-only. None has exhaustive full-page gold. Prior source
books were already explored, so the new page IDs are not pristine unseen books.
There are 100 target page cases and 101 processed pages: an inherited-form input
retains one extra unscored page to preserve its original AcroForm. This was not
one 100-page upload. Original source/gold hashes verify unchanged.

Native output met 26/54 prior content checks. Four of six quarantine sentinels
passed; two required specific issue codes that were absent even though those
pages remained held. Seventeen other checks remained manual. On six newly reviewed real pages it met 12/22
named checks, with eight mismatches and two manual checks. It met 1/11 new
authored content checks. The experimental path preserves all 100 native Markdown
prefixes and leaves these native scores unchanged; appending proposals is not a
completed source repair. Every named native mismatch was held, but 90 holds out
of 100 cases also show the review burden. Zero selected unheld mismatches does
not establish a general false-accept rate.

Of 13 selected equations with bound region gold, v1 discovered/proposed 11.
Two scans had only `pdf_ocr_review` issues, which the prototype initially omitted
from its route. Corrected v2 routes both and finds both equations. Only those
two affected scans were rerun; the 100-case v1 timing is not relabeled as v2.
The API trials below use v2. Geometric matching uses a post-hoc IoU >= 0.2 to
accommodate annotation margins; this is a partial diagnostic, not exhaustive
region recall or detector AP. Twenty earlier equations lack region gold and are
excluded from region-bound proposal scoring.

The unchanged strict expression checker matches 2/13 proposals. Supplementary
Codex inspection against the frozen sources/gold finds 10 usable equivalents
after the two v2 reruns; this is post-output engineering judgment, not a blinded
human accuracy benchmark. The other three have prose inside a math boundary,
malformed LaTeX, and a wrong dotted-background equation respectively. The Bell
state signs and sample-variance denominator/mean/square are promising examples;
unreviewed proposals elsewhere include malformed commands and invented symbols.
The 10/13 result does not describe all 447 proposals. Tables, merged cells,
diagram relationships and page completeness remain unresolved.

All proposals retain blocking issues. The prototype appends them only to test
source retention and quarantine; a production adapter should keep candidate
repairs separate from canonical Markdown until explicitly accepted.

## API and recovery

The actual FastAPI app, upload route, serial extraction worker, local job/store
and review/version endpoints were exercised at 1/2/4 concurrent clients. Each
backend completed 96 jobs: 69 measured, 24 replay seeds and three warmups, over
eight fixed inputs. All retained original bytes, exact-version Markdown and
block spans, and all support-policy checks passed, including seeds/warmups.
This is 192 jobs over repeated inputs, not 192 independent documents. Compilation
used explicit `MockCompilerModels`; no provider calls or semantic compilation
quality/performance claims are included.

| Concurrent clients, fresh extraction cache | Native median / p95 | Model path median / p95 | Model upload + queue wait p95 |
| --- | ---: | ---: | ---: |
| 1 | 1.42 / 1.78s | 4.50 / 18.17s | 0.35s |
| 2 | 1.74 / 2.34s | 8.22 / 11.76s | 7.87s |
| 4 | 3.36 / 4.59s | 11.93 / 20.36s | 16.62s |

The model remains resident across cohorts: only the first cohort includes its
initial load. More clients feed the same one-worker queue; they do not provide
parallel extraction. Queue wait is measured from request start to extraction
start and includes upload/dispatch overhead. Percentiles describe one small
eight-case cohort, not service SLOs or statistically stable tail estimates.
Warm new-content cohorts have zero extraction cache hits and exclude the first
prose warmup, so their input mix differs; full data are in the JSON receipt.

| Concurrent clients, renamed identical-byte replay | Native median | Model path median | Cache hits, native and model |
| --- | ---: | ---: | ---: |
| 1 | 1.27s | 1.43s | 8/8 and 8/8 |
| 2 | 1.49s | 2.01s | 8/8 and 8/8 |
| 4 | 3.07s | 4.12s | 8/8 and 8/8 |

Replays retain review holds. Separate loopback **TCP HTTP** through single-process
Uvicorn also passed: a real upload queued before shutdown was recovered by a new
application/worker instance, and retained evidence/holds were verified. The load
cohorts use in-process Starlette HTTP transport; they are not a browser, TLS,
public network, multi-host durability or sustained overload test.

All 12 focused robustness checks passed: renamed-source cache reuse; changed
region budget and injected model-hash identity misses; corrupt cached Markdown
rejection; real model-phase deadline/kill with no cache result; new-process
recovery; idle model crash/restart; TCP upload; queued-job restart recovery; and
retained bytes/Markdown/spans/holds. The model-hash test injects a changed identity
without modifying read-only weights. The prototype bounds model inference, not
the entire native extraction or API job.

Before public use, add queue limits/backpressure, document budgets and an overall
job deadline with cancellation/cleanup. The current worker has no cancellation
API, unbounded process-local queuing and no durable exclusive job claim. Multiple
Uvicorn workers are not a safe scaling recommendation for the current stores.

## Implementation decision and evidence

Use the maintained Paddle [layout](https://www.paddleocr.ai/main/en/version3.x/module_usage/layout_detection.html)
and [formula recognition](https://www.paddleocr.ai/main/en/version3.x/module_usage/formula_recognition.html)
APIs behind an explicit optional adapter. Keep models preloaded in an isolated,
bounded worker and reuse source/config/model/version-bound caches. The measured
dependency/model closure does not justify copying these implementations into
the standard-library-only core. Further broad product shopping is lower priority
than integration safety and fuller independent gold; test GPU-hosted larger
models later if fully automatic high-fidelity PDFs are required.

No production backend, default, dependency, public deployment, commit or release
changed. Experimental code, private documents/gold, model logs, complete pip
freeze and receipts remain in the education checkout's ignored
`engine/out/website-pipeline-2026-10-26/`. Its Dockerfile and scripts record the
procedure. A public checkout cannot reproduce the private-source accuracy panel.
The [aggregate JSON receipt](website-pipeline-2026-10-26.summary.json) contains
counts, timings, hashes and limitations without source excerpts or local paths.
The [earlier OCR comparison](ocr-benchmark-2026-10-24.md) retains the wider
candidate evaluation and its different crop/page scopes.
