# Packaging fixtures

These four invented sources are copied unchanged from the education repository's
held-out and synthetic Office/PDF fixtures. They contain no local textbooks or
provider captures. `packaging-baseline.json` records seven conversions captured
before module separation, compared on Markdown, source blocks, issues, status,
review status, and page count. It checks refactor compatibility, not independently
verified extraction fidelity. Pandoc expectations use version 3.10.

The reuse integration retains this original snapshot. The parity test permits
only two explicitly reviewed TeX whitespace edits in algebra.pptx, with exact
corresponding offset adjustments. All other content, locators, blocks, issues,
statuses and page counts still match the original capture.

The files are included in the source distribution for tests, not the runtime wheel.

`ordinary-multi-column.pdf` is an unchanged copy of the application's invented
ordinary-PDF control. Its six numbered steps run down the left column, then down
the right column; the qualification below both columns follows step 6. SHA-256:
`21c657a27e31ff9ef92dbd61e186df5ed11975ddc6b847761409ab17293c8f54`.

`table-controls.pdf` is the unchanged five-page invented control from the
application's table-library evaluation. Its independently authored cells and
spans are retained in `table-controls.json`; expectations predate the converters.
Pages cover ruled and borderless grids (empty cells, recorded zeros, repeated
rows), a merged header, aligned instructional prose and ordinary prose. The
merged header has a two-column Readings cell and a two-row Status cell. The
original rendered page was inspected during the 2026-11-04 repair; this is an
agent source check of an authored control, not real-document/human acceptance.
Source SHA-256: `d7cf7dc1c9d8b2757878c0711c2e9ab82fbe1b1c22776b06d3179f0d59e30a9c`.
