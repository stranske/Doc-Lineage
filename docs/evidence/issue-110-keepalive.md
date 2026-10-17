# Issue 110 keepalive validation

Validated on 2026-10-17 with Python 3.14.8, starting from `4532945`.
The original evidence under `issue-110/` remains unchanged.

- [x] Focused public CLI creation, fresh-process ID-only export, native DOCX
  accept/reject reconstruction, and file-pair compatibility: **61 passed**.
  The original checklist's 54-test result is historical; the pre-change suite
  here passed 59 tests. Two new cases verify successful binary stdout exports
  through the real renderer, one for each invocation form. File exports still
  verify their status message, and all four cases verify source/record preservation.

Command:

```sh
pytest tests/test_cli.py tests/export/test_docx_redline.py tests/export/test_docx_redline_golden.py -m 'not slow' -q --junitxml=/tmp/issue-110-keepalive-focused.xml
```

Ruff 0.17.1 passed `ruff check .`. Mypy 2.4.0 passed
`mypy --follow-imports=silent src/doc_lineage/blackline.py src/doc_lineage/cli.py`.
Black 26.10.1 formatted the changed test and passed the required repository gate:

```sh
BLACK_CACHE_DIR=/tmp/issue-110-black-cache BLACK_NUM_WORKERS=1 black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
```

All 158 Python files passed individual Black checks first, populating this cache.
This avoided sandbox worker failures: the default process pool could not create
its socket, and uncached single-worker checks stalled. The complete gate then
exited zero with 158 files unchanged. Installed tool versions match the dev pins.

This round completes the first checklist item only. The SHA-256 mutation exercise,
isolated full suite/coverage, repository-wide mypy, and portable replay were not
rerun; their original evidence and limitations remain historical.

Committing is blocked by the sandbox's read-only `.git` mount. Attempting
`git add -- tests/test_cli.py` failed creating `.git/index.lock` with
`Read-only file system`. The verified test changes remain in the working tree.
