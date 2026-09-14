# PR #22 autofix diagnosis

## Attempt 2: missing styles part in the synthetic fixture

Gate run: https://github.com/stranske/Doc-Lineage/actions/runs/34802722408
Head: e5c46fa0dca61486d2a8400a429a3c7ef7997c30

The new diagnostics in jobs 103848552172 (3.12) and 103848552181 (3.13)
both expose `Error: Value cannot be null. (Parameter 'part')` from Docxodus
0.3.0. Each job has one failing golden test and 14 passing tests; coverage
is 100%. This is a native comparison failure, not a finalization defect.

The synthetic DOCX omitted `word/styles.xml`. Upstream comparison code reads
`StyleDefinitionsPart.GetXDocument()` without checking for a missing part:
https://github.com/JSv4/Docxodus/blob/main/Docxodus/WmlComparer.cs
(see `CopyMissingStylesFromOneDocToAnother` and `AddFootnotesEndnotesStyles`).
This is the likely cause of the null-part failure; the native error does not
include a stack trace identifying the exact call.

Added a minimal Normal paragraph style, its content-type declaration, and the
document relationship to both synthetic inputs. All existing semantic redline
assertions remain in place. No production or workflow changes were needed.

Validation: all 15 tests pass with 100% coverage using
`XDG_CACHE_HOME=/tmp/doc-lineage-autofix-cache python -m pytest -q`.
Ruff, Black, and `git diff --check` pass. Local Python is 3.14.7 and the
installed native engine is still 1.0.0. Installing 0.3.0 into an isolated
temporary directory failed (no matching distribution available in this
environment), so the fix needs confirmation on CI Python 3.12/3.13 with the
locked engine. The smallest check is
`python -m pytest tests/export/test_docx_redline_golden.py -q`.

PR #22 was verified open and ready (`draft=false`) at the head above.

## Previous attempt

Gate run: https://github.com/stranske/Doc-Lineage/actions/runs/34802341248
Head: d1a738ec2fc6c6c23eb256700aaeb522bd48a0fc

Both Python 3.12 and 3.13 fail
`tests/export/test_docx_redline_golden.py::test_tracked_changes_present` because
the Docxodus executable exits 1. Each run reports 14 passing tests and 100%
coverage. Lint, formatting, and mypy pass. Finalization reports the pytest failure.
The traceback does not expose the captured native stdout/stderr.

CI installs `python-redlines-docxodus==0.3.0`; the available local environment
has 1.0.0. All 15 tests pass locally on Python 3.14 with
`XDG_CACHE_HOME=/tmp/doc-lineage-autofix-cache python -m pytest -q`.
The cache override is necessary because the local home cache is read-only.
Installing the CI engine version failed because PyPI DNS/network access is
unavailable. The native failure's underlying cause is still unknown.

The golden test now adds captured stdout/stderr to the original exception and
re-raises it, preserving all assertions. Ruff and Black pass for the changed test;
source mypy also passes.

Next step: rerun the golden test with the locked 0.3.0 engine on Python 3.12/3.13
and use the exposed native diagnostic to make a targeted repair. Do not treat
the local 1.0.0 pass as proof that CI is fixed.

Posting this diagnosis and adding `needs-human` were attempted, but both GitHub
mutations require tool approval and this run has approval policy `never`.
PR #22 was verified open and ready (`draft=false`).
