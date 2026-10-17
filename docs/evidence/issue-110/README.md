# Issue 110 implementation evidence

This directory contains raw local logs, real pytest JUnit, source hashes and the
synthetic DOCX inputs/output captured from the public CLI test. `validation.json`
names actual commands, counts, exits and limitations. `SHA256SUMS` covers all
retained evidence except itself; `source-hashes.json` binds the validated code.
The implementation commit is the Git commit containing this evidence.

- `focused.xml`: 54 passed, including real native ID-only and file-pair export.
- `red.xml`: 4 failures at `SHA256_CHECK_DISCONNECTION` after disabling only the
  SHA-256 mismatch condition in `_run_export_docx`; both roles and both outputs.
- `green.xml`: 25 comparison tests passed after byte-identical CLI restoration.
  `mutation.json` records original, mutant and restored source hashes and argv.
  `capture_mutation.py.txt` retains the actual capture driver, including its
  `finally` restoration; its absolute root names the original capture location.
- `full-isolated.xml`: 503 passed; coverage 89.02%, unchanged 80% floor.
- `full.xml.gz` (raw JUnit, gzip-compressed): initial full-run failure is retained, not relabeled PASS. Its sole
  failed test attempted an editable pip install into the read-only shared Python.
  The same unmodified test and full suite passed in an isolated temporary venv.
- `mypy.log`: full type check remains FAIL (two unused ignores in unchanged
  `docling_segmenter.py`); the source hash matches base `45971929b534d953e1c56ffb42b4bdfc3fd4b994`.
  `mypy-changed.log` checks the two changed modules with silent imported modules;
  it does not establish a clean repository-wide type check.
- Ruff and Black passed with the installed versions. Those versions and mypy
  are older than the dev pins; exact pinned-version validation remains unknown.
- `advisor.json` and `advisor-declines.json`: opener-lane consultation and reasons
  for declining gated/missing-fact capabilities. Consultation used a captured
  registry copy after the sandbox denied the live ledger lock; no live ledger
  heartbeat or capability dispatch is claimed.

Run `/bin/sh docs/evidence/issue-110/replay.sh /absolute/path/to/python` from a
checkout with its dependencies installed. It verifies the retained original
package digests, explicitly creates a NEW record with relocated paths, reopens
it in another process, exports a real DOCX and uses the existing golden helpers
to reconstruct both accepted and rejected revision text. Output is retained in a
printed temporary directory. It does not rewrite or silently relocate the raw
captured record. Engine output ZIP metadata can vary; semantic reconstruction is
the reproducibility gate, rather than byte-identical regenerated redline hashes.

`artifacts/artifact-manifest.json` is a synthetic preservation sentinel, not an
ingest claim. The test verifies unchanged sources, record and sentinel before
and after export. DOCX/package comparison is distinct from extracted-PDF
comparison; no PDF conversion or new renderer is implemented.

`full.log.gz` and `full.xml.gz` preserve the first failing run byte-for-byte
without treating pytest traceback whitespace as source whitespace. Decompress
with standard gzip tools; uncompressed raw originals remain in the run directory.

## Current bounded review recovery

Original4532945 delivery is historical component evidence, with its original source hashes and artifact checksum list retained as source-hashes.initial.json and SHA256SUMS.initial.txt. The original replay source is replay.initial.sh.txt; its historical name in the initial checksum list refers to that old script. Current source-hashes.json binds the changed source/test/replay, and current SHA256SUMS binds the current evidence directory. The subsequent native6201 payload is preserved. Current review controls and validation live separately in ../issue-110-review; no old full-suite or mutation receipt is relabeled as a new execution.
