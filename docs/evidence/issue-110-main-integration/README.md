# Issue 110: current-main integration of existing PR 127

This is a conflict-only integration of prior `89542e1103330e076ce1afad24091e3428fd56ee`
and main `aa2351f72636e76f80b4e0013e9a099b2d9a495b`. The read-only reproduction in
`merge-tree.txt` shows that **CLI**, rather than README, was the actual conflict.
README auto-merged native DOCX comparison-by-ID documentation with the documented
management-fee extraction subset, unresolved output, and fidelity limits. The
resolution retains the original comparison dispatch and exact main extraction
handler; no new product logic was added. `preserved-payloads.json` proves that
removing only main's import/parser/handler additions restores the original CLI.

## New verification

- 228 focused CLI/store/export/ingest/blackline/packaging regressions passed.
- Full normal suite: 567 passed, zero failures/errors/skips; coverage 90.64%
  against the unchanged 80% floor. Original test/assertion and exclusion rules
  remain intact. The two inherited pandas dependency warnings remain in the logs.
- Ruff and Black passed. CLI mypy passed with silent imported-module analysis.
  Full mypy still fails on the two unused-ignore errors in unchanged
  `adapters/docling_segmenter.py:111-112`; hashes agree with both merge parents.
- Isolated Anaconda system-site-packages venv; editable install used
  `PIP_NO_BUILD_ISOLATION=0 PIP_NO_DEPS=1`. No shared interpreter was modified.
  Exact repository Ruff/Black/mypy pins were unavailable in this runtime and
  are not claimed as verified. See `environment.json` and command receipts.
- The original 64/513/4-RED recovery evidence remains historical and byte-intact.
  No new causal mutation was appropriate for this conflict-only integration.

`native/` holds genuine synthetic DOCX packages, original/modified/result XML,
actual absolute executable paths, argv, before-invocation hashes, exit results,
and diagnostics for 26 captured helper invocations. Each captured binary matches
SHA-256 `12b0955111e348543e55ac9fbc06599b3e79294781198c6fb1b46f3029867c36`.
The installed 1.0.0 archive matches
`c231bd1aefa7af56932cf0aebbd7a0fbe8cf1143eb3baff6abf42dc426c04571`.
The parent verified ad-hoc signing/no Team ID; publisher remains UNKNOWN.
No helper download, native access failure, OS prompt, Office, private corpus,
or deployment occurred. Initial focused children overrode PYTHONPATH before the
observer was placed in the isolated venv; their native invocations were not all
captured. The full normal suite began after that correction. Captured execution
counts are not presented as an exhaustive count of the earlier focused startup.

`preserved-payloads.json` and `key-source-hashes.json` retain exact source/fixture/
evidence hashes. `blackline.py` remains SHA-256
`d99738ce7c1975b4450c88731cb0773f101f5786bec884fae57f5368f72f5270`.
Main only appends tests to the prior export and ingest files; its packaging
assertion now expects 28 instead of 27 tests and includes the PDF fixture.
The original native/file-pair/ID/stdout/file-output and export paths are retained.
Pyproject is identical to both parents; MANIFEST only adds main's PDF fixture.
No workflow/shared-schema files or sibling branches were changed.

`ownership-prebranch/` contains all PR/source comments and decoded records across
all heads. Four recorded workflow attempts, including main workflow_dispatch,
were inspected directly: all actual implementation jobs are terminal. Three
attempts succeeded; the later Claude dispatch failed because the command was
unavailable. The expected guardian and dispatcher claims were preserved. The
source creator's actual rc=0/release_rc=0 terminal receipt is retained separately.
Ownership/comments and the expected remote head are refreshed again before push.
No PR creation/closure/merge, source closure, CI waiting, or acceptance-scope
change is performed by this integration. Parent owns claims/pause and closeout.

The required capability consult used actual task words and exact opener lane,
surface and repository flags. It failed on the sandbox-denied shared ledger lock;
this is a fail-open error, with zero offers or declines returned. The initial
bare-directory fetch also hit its FETCH_HEAD write boundary; the requested
worktree metadata fetch then succeeded through detached-net from outside the
checkout. Git also emitted packed-refs lock errors while starting the merge;
the merge index and parents were independently verified. These were filesystem
sandbox errors, not macOS prompts. Source/test/README/MANIFEST whitespace checks
pass; historical incoming PDF and raw-log whitespace is retained unchanged.

Hosted CI, provider PASS, native Word rendering, deployment, and final source
acceptance remain UNKNOWN. The final remote push/ready-state receipt and the
handoff entry are returned to the parent without releasing its guardian/pause.
