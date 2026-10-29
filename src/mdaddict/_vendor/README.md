# Vendored Office-math parser

`omml2latex.py` is the unmodified `omml2latex/_parser.py` from
[omml2latex 0.1.1](https://pypi.org/project/omml2latex/0.1.1/), by INSEONG LEE,
Copyright 2026, Apache 2.0. The release wheel contains a LICENSE and no NOTICE.
The full license and attribution ship in both mdaddict distributions.

- [Release wheel](https://files.pythonhosted.org/packages/aa/66/528fd921508c4a84c4d7f2cc6bf1ae45c96a387081d90e3a60d3e4a1a245/omml2latex-0.1.1-py3-none-any.whl)
- Wheel SHA-256: `b24a13f4a14791662972d1b6716e5a1f9114891ccf1a96622f61dbfb1c300bd4`
- Parser SHA-256: `1ea42deb02b417573872a448d836c283e964a963a4d546a627c1761b1ecf26f1`
- License SHA-256: `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

The copied component imports only the Python standard library. Its CLI, document
loader and package entry points are omitted. No local parser modifications have
been made. Keep the upstream file intact, including its comments and long-file
structure, to make updates auditable. Compatibility handling lives in
`../office_math.py`: validation, bounded copying, literal escaping, source-based
boundary spacing and redundant single-base brace normalization.

The benefit is native PowerPoint equation conversion without launching Pandoc,
while keeping the core dependency-free. Source-defined equation controls and
PowerPoint source-span tests cover the integration. Unsupported structures use
the existing Pandoc fallback when installed, otherwise an unresolved issue.
This is not a claim of complete Office-math fidelity. Upstream approximates some
styling and uncommon operators; model/fidelity evaluation remains separate.

To update, verify the release archive hash against PyPI metadata, compare the
parser and license, review dependency imports and notices, update these hashes,
and rerun the equation, format-parity and installed-distribution checks.
This component's license does not select the license for mdaddict itself.
