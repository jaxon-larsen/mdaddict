# Decimal preservation guard — 2026-10-23

The compatibility PDF path could change a native decimal into differently grouped
digits while returning `success` without an unresolved issue. The research-paper
sentinel for `1.1M` reproduces this: the table emits `11M<br>.<br>1M`. A page-wide
character inventory cannot distinguish that corruption because the characters
still occur elsewhere in the result.

## Change

Compare native decimal-token multiplicity with the converter's Markdown before
recovery excerpts or recovered code can mask the loss. Missing tokens produce
`pdf_numeric_unresolved`, linked to the existing page block. The issue remains
blocking under the shared policy even if a retained record labels its severity
informational. Cached results retain the same issue and source spans. Application
publication checks reject claims supported by that page; independent pages remain
eligible under the existing validators. Old acceptance metadata cannot clear it.

The guard does not rewrite the table, infer the intended number, or certify
numeric meaning. It checks decimal groups and repetition, not all integers,
signs, units, exponent relationships, locale conventions, or equivalent formulas.
Already-split native tokens can escape it, and valid alternate representations
may require source review. Multi-part version numbers are excluded. It adds no
dependency, provider call, source-contract field, or new public option.

## Source-backed verification

A fresh paired run reused all 16 originals, 29 reviewed pages and unchanged gold.
Every reviewed page's Markdown and all original check verdicts remained identical
to the [initial corpus comparison](pdf-corpus-2026-10-23.md).

| Result | PDFium | Compatibility |
|---|---:|---:|
| Content matches | 26/54 | 43/54 |
| Held reviewed pages | 22/29 | 16/29 |
| Stable cache replays | 18/18 | 18/18 |
| Unheld pages with known content mismatches | 0 | 1 |

Compatibility now holds the previously unheld DART page 11. Demsar page 11 gains
the numeric issue while remaining held for prior reasons. Actual publication
probes on both numeric-issue pages reject dependent claims. No content accuracy
improvement is claimed; the new behavior prevents the measured decimal defect
from bypassing review. The ordinary multi-column control still has an unheld
whole-content ordering mismatch and remains an explicit open defect.

Follow-up: the [numbered-column correction](reading-order-2026-10-23.md) resolves
that control and raises compatibility content matches to 44/54 without changing
the 16/29 hold count. This receipt records the earlier decimal-guard snapshot.

Private evidence: `education/engine/out/numeric-guard-2026-10-23/` contains
`before.json`, fresh backend reports, `comparison.json`, `distribution.json`,
the reproduction script and isolated installed-wheel environment. Earlier corpus
and LiteParse evidence were not overwritten. Originals/imported gold hashes
were checked before and after the fresh run; all AI request counts were zero.

## Tests and distribution

Nine package regressions cover grouped decimals, multiplicity, presentation,
version strings, legacy severity, page scoping and cache replay. Two application
cases cover blocking despite old acceptance and informational severity, with an
independent page still eligible. The focused package/review set passes 16 tests.

The installed-wheel package + engine + API run on Windows Python 3.13.7 passes
**775 tests, 30 subtests**, with **5 skips**. The first combined source runs exposed
cross-test helper imports and absent optional extras in the chosen API environment;
the completed run uses an isolated environment with the built wheel, all native
extras, existing API dependency versions, and explicit helper import paths:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = 'engine/src;api/src;engine;api/tests;engine/tests/extract'
$env:PATH = 'C:/Program Files/RStudio/resources/app/bin/quarto/bin/tools;' + $env:PATH
engine/out/numeric-guard-2026-10-23/integration/Scripts/python.exe -m pytest engine/tests api/tests ../mdaddict/tests --import-mode=importlib -q
```

Use your installed Pandoc location. The retained `api-third-party.txt` binds the
API dependency versions used to prepare this evaluation environment.

Fresh distribution checks outside the checkout pass:

| Profile | Tests passed | Skips |
|---|---:|---:|
| Core, including dependency-free CLI/import smoke | 40 | 21 |
| PDF, explicitly without PyMuPDF | 49 | 19 |
| PDF compatibility | 43 | 18 |

Profile skips reflect unavailable unrelated extras and external tools; the full
run exercises both PDF paths. Existing OCR, Linux/macOS and release/license gates
are not cleared by these results. No model or OCR quality test was run.

Build from source distribution and strict Twine checks pass. The wheel's runtime
and resource bytes match current source. Artifacts under
`out/numeric-guard/dist/`:

- Wheel: 108,810 bytes, SHA-256
  `26d68d07fb2eafed74a70d65020c5553195b0672de7e7a0605bf9146276f28d2`.
- Source distribution: 194,284 bytes, SHA-256
  `a8c4aa28164422946217af40287540418b0894477f612b4cfd35866099d75d70`.

Changes remain local and unstaged. No commit, push or publication occurred.
