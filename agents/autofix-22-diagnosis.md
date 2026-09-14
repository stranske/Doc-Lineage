# PR #22 autofix diagnosis

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
