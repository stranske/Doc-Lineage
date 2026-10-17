# Pairing confidence follow-up

The original evidence in this directory describes the implementation at
`d0ef0da`. This follow-up fixes a boundary case in `align_sections`: a non-finite
header confidence must require manual review even when the caller selects a
zero threshold. Sanitized confidence remains zero in emitted lineage records.
Finite confidence equal to the threshold still permits automatic pairing.

Validation on the current runner uses Python 3.14.8. The requested
`/opt/anaconda3/bin/python3` is absent, so its interpreter-specific results
cannot be reproduced here. These are fresh checks using the available runtime,
not replacements for the original receipts:

- [x] `python -m pytest tests/blackline/test_section_id_pairing.py -q -m "not slow"`
  passes: 23 tests, including NaN and both infinities on either side at zero
  and default thresholds. Before the production fix, six new cases failed.
- [x] `python -m pytest tests/blackline/test_comparison_run_cli.py tests/test_cli.py
  -q -m "not slow"` passes: 43 tests, including independent PDF ingest,
  comparison, and lookup processes.
- [ ] Full isolated suite acceptance remains unmet: 501 passed, 13 failed,
  with 88.58% branch-aware coverage against the unchanged 80% floor. The venv
  inherits installed packages and uses `PIP_NO_BUILD_ISOLATION=0 PIP_NO_DEPS=1`.
  `pypdfium2` is absent, preventing OCR page rendering; installation of the
  existing optional dependency failed because the configured package source
  supplied no matching distribution. No tests or coverage exclusions changed.
- [x] Disconnecting the actual production `_section_comparison` call to
  `align_sections` causes the unchanged named persisted-pairing regression to
  fail its `PERSISTED_SECTION_PAIRING_MUST_CALL_EXISTING_ENGINE` assertion.
  Restoring production bytes exactly makes the same regression pass. Test
  hashes remained unchanged during this check.
- [x] Ruff 0.17.1 and Black 26.10.1 pass for `src`, `tests`, and `replay.py`.
  The repository-wide Black gate also passes for all 160 Python files.
  Black's multi-file execution hangs on uncached files in this sandbox, so
  single-file Black checks populated a writable `BLACK_CACHE_DIR` before the
  required whole-repository check with `BLACK_NUM_WORKERS=1`.
- [x] `python -m mypy src` passes with mypy 2.4.0: 38 source files. These
  installed Ruff, Black, and mypy versions match the development pins.
- [x] Portable replay and lookup of the existing public comparison artifact
  both pass. Original public artifacts and their receipts remain unchanged.

Fresh raw JUnit XML, the full coverage XML/log, production mutation patch and
red/green JUnit XML, and replay argv records are under
`/tmp/doc-lineage-112-mt4TLo/` for this runner session. They are temporary local
captures; this follow-up does not claim refreshed normalized public receipts or
remote writer terminal receipts.
