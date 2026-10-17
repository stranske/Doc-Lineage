# Issue 110 task reconciliation

Reviewed commits `4532945` and `714ef2c` on 2026-10-17. The comparison-record
implementation and README contract were already present. The first verification
run passed all 61 existing focused tests. This follow-up extends the golden
round-trip test to exercise comparison-ID exports as well as direct rendering
for insertion-only, deletion-only, unchanged, and Unicode/XML text.

The following reflects verified local implementation. The PR body remains
unchanged because its update required tool approval, unavailable under this
run's `never` approval policy. A complete proposed PR body is saved at
`/tmp/doc-lineage-pr-127-body.md` for the authorized publisher.

- [x] README comparison-record fields, ID generation, store, and verification contract.
- [x] Ordered record writing and ID loading, including unknown-ID rejection.
- [x] CLI comparison creation and ID export with boolean file-pair compatibility.
- [x] Reopen sources and verify the same SHA-256-bound buffers passed to the renderer.
- [x] CLI tests for creation, process reopening, ID-only export, and failure cases.
- [x] Golden accept/reject reconstruction assertions for ID-driven exports.
- [x] Comparison CLI acceptance command passes: 27 passed, 20 deselected.
- [x] Deliberately bypassing SHA-256 verification fails all four changed-bytes cases.
- [x] A filesystem path as the blackline value fails with `Not a comparison ID`.
- [x] Entire CLI suite passes; README describes the implemented ID workflow.

Validation commands (all successful after restoring the production source):

```sh
pytest tests/test_cli.py -k comparison -m 'not slow' -q
pytest tests/test_cli.py tests/export/test_docx_redline.py tests/export/test_docx_redline_golden.py -m 'not slow' -q
BLACK_CACHE_DIR=/tmp/doc-lineage-comparison-black-cache BLACK_NUM_WORKERS=1 black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
ruff check tests/export/test_docx_redline_golden.py
git diff --check
```

The focused suite passed **65 tests**, including the complete 47-test CLI suite.
Black 26.10.1 left all 158 Python files unchanged. Its default worker pool was
sandbox-blocked, so individual file checks populated the cache before the
single-worker repository gate. Ruff 0.17.1 passed.

During the deliberate-break gate, the SHA-256 condition was temporarily replaced
with `False`. All four cases failed specifically with
`SHA256_CHECK_DISCONNECTION: changed bytes were exported`, rather than an unrelated
engine error. The CLI was restored byte for byte to SHA-256
`343a5cb865801f8fda1885adb4227b6f208a99e0f8972b882c6d784478998fdd`
before rerunning the green commands. Mutation and green JUnit/log artifacts are
under `/tmp/doc-lineage-comparison-*`.

PR #127 was verified open and ready for review (`draft=false`).

Commit publication was attempted after the checks passed. `git add` failed to
create `.git/index.lock` with `Read-only file system`; no commit was created.
The attempted blocker comment and `needs-human` label were also rejected by the
GitHub tool's approval requirement. An authorized publisher must commit the
golden-test change and this reconciliation, then apply the proposed PR checklist.
