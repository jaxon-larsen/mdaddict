# mdaddict

This repository owns the offline-first file-to-Markdown package, its public
Python API and CLI, native format adapters, and optional AI repair protocol.
Use `mdaddict` in all public-facing names and documentation.

Default backend selection must prioritize permissive dependencies suitable for
proprietary/commercial consumers without a separate paid dependency license.
The current PyMuPDF backend is under review against this requirement; do not
describe the current stack as having completed license clearance. Model-based
backend evaluation is deferred until the user asks for it. Reuse established
implementations. The user favors copying bounded, useful components where this
improves the package; vendor with documented provenance,
dependency closure, license/notice review, and a demonstrated benefit.
The copied OMML parser remains byte-identical to upstream; keep local validation
and compatibility handling in office_math.py. Markdownify uses its public API
through the optional html extra, with Pandoc retained for complex content.
Public pdf/all extras use PDFium and exclude PyMuPDF; the education app opts into
all,pdf-pymupdf explicitly for compatibility. Auto still prefers an installed
PyMuPDF stack during transition. PDFium's vector/math capability guards retain
unresolved holds; do not replace relationship checks with cell-word presence.
PDF AI repair currently requires explicit PyMuPDF selection and its optional
extra. A provider on the PDFium path must fail clearly before importing PyMuPDF
or making model calls.

Keep the core standard-library-only. Import format dependencies lazily and keep
them in optional extras. No automatic downloads, provider selection from the
environment, or model calls without an explicitly supplied adapter. Preserve
supported formats, source spans, issue semantics, and schema compatibility.

Run `python -m build .` and `python -m twine check --strict dist/*` to validate
artifacts. `python tests/check_distribution.py --extra core` verifies an installed
wheel outside the checkout. Repeat for each extra; `all` requires Pandoc and
Tesseract. Use deterministic model doubles for tests; live calls require explicit
authorization. Passing structural tests does not establish source fidelity.

Leave changes unstaged and uncommitted unless the user explicitly requests
staging or committing. Do not publish to PyPI or dispatch the publishing workflow
without an explicit release request. Stop and report after three consecutive
failed verification attempts instead of repeating an unsuccessful approach.
