# Publishing mdaddict

Repository: https://github.com/jaxon-larsen/mdaddict

The GitHub Actions environment `pypi` has been created. Configure the PyPI
pending trusted publisher with these exact values:

| Field | Value |
|---|---|
| PyPI project name | `mdaddict` |
| Owner | `jaxon-larsen` |
| Repository name | `mdaddict` |
| Workflow name | `publish-mdaddict.yml` |
| Environment name | `pypi` |

The workflow filename is entered without `.github/workflows/`. The workflow's
publish job uses the matching environment and job-scoped `id-token: write`.
No long-lived PyPI API token is needed. See the [PyPI setup documentation](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
and [publishing documentation](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
Adding a pending publisher does not reserve the project name or upload a release.

## Before the first release

Settle the project license and dependency-license review. Add the chosen license
text in `LICENSE`, its SPDX expression in `project.license`, and
`project.license-files = ["LICENSE"]` in `pyproject.toml`. Licensing remains
undecided; the publishing workflow deliberately rejects missing license metadata.
Keep `src/mdaddict/_vendor/NOTICE`, its README and the full upstream license in
both distribution artifacts. The copied OMML component's Apache 2.0 license
does not select the project license. `[pdf]` and `[all]` use PDFium; the optional
`[pdf-pymupdf]` stack requires a separate dependency-license review. Verify clean
permissive-only installs and their unresolved-content behavior before release.

Commit and push the prepared sources and workflows to `main`. Run the cross-platform checks and inspect
the results, including OCR integration. Build the wheel from the source
distribution and run strict metadata checks:

```console
python -m build .
python -m twine check --strict dist/*
python tests/check_distribution.py --extra all
```

For reproducible pre-commit evidence, `python tools/verify_distribution.py
--profiles core pdf pdf-pymupdf office images html extended captions heif online all
--out out/verification-release` freezes tests and source before building once.
It keeps hashes/logs in the fresh output directory. The CI check matrix uses
this verifier. Release execution still uses the separately approved publishing
workflow; successful local verification does not publish anything.

Review repository environment protections appropriate to the maintainers. The
environment exists; no required-reviewer protection has been configured here.

## Publishing an approved release

Update `project.version` and `mdaddict.__version__` together. The current
distribution checker targets version 0.1.0 and must be updated for later releases.
From GitHub Actions, manually run **Publish mdaddict** on `main`, supplying the
exact version, such as `0.1.0`. The workflow checks version/license metadata,
runs the full installed-distribution CI matrix, builds artifacts once, and passes
those artifacts to the trusted-publishing job. That job uploads to PyPI.

Creating this repository and configuring its environment do not run the workflow
or publish a package. Release execution still requires an explicit request.
