# PR130 bounded evidence harness recovery

Expected start: `e46a58cbe00f01593310cdf66534fd4ce20dc079`.
Audit-only source113 findings remain report-only. Production, schemas, workflows,
product behavior and original scope tests were not changed by this recovery.
No new issue, branch/PR, merge, closure, Office, Brain/state service or hosted
acceptance is part of this work.

## Exact finding dispositions

| Finding | Disposition and proof |
| --- | --- |
| [4302676649](https://github.com/stranske/Doc-Lineage/pull/130#discussion_r4302676649) | FIXED: mutation success receipt is written only after named RED/restored GREEN, exact production restoration and unchanged-test validation. Invalid exit/marker/GREEN and GREEN-time test edits raise without `mutation.json`; failure logs remain. Genuine refreshed `mutation/` is 2 RED assertion failures, 2 restored passes. |
| [4302676655](https://github.com/stranske/Doc-Lineage/pull/130#discussion_r4302676655) | FIXED: probe records only TypeError, SystemExit, ValueError. NameError, AttributeError, ImportError and RuntimeError propagate in rejection controls. Historical probe was genuinely rerun at its designed BASE in a detached temporary local checkout. |
| [4302676659](https://github.com/stranske/Doc-Lineage/pull/130#discussion_r4302676659) | FIXED: explicit commit-object availability check names historical BASE and chains the missing-object exception. Other Git failures retain their original error, including non-repository/I/O failures; production diff guard remains. Real empty-repository and other-error controls pass. |
| [4302676677](https://github.com/stranske/Doc-Lineage/pull/130#discussion_r4302676677) | FIXED: each child has a 300-second timeout. Timeout records exact argv, timeout, null exit, status, partial stdout/stderr before raising with cause; successful earlier receipts remain. Nonzero child failures remain durable. Actual three-process legal replay passed. |
| [4302676682](https://github.com/stranske/Doc-Lineage/pull/130#discussion_r4302676682) | FIXED: blank lines accepted, malformed/hex/duplicate entries rejected, absolute/traversal/escaping-symlink paths rejected, every evidence file listed exactly once. SHA256SUMS explicitly excludes itself; missing/unlisted/corrupt/self entries fail. |
| [4302676688](https://github.com/stranske/Doc-Lineage/pull/130#discussion_r4302676688) | FIXED: actual testcase counts and declared suite totals agree, real suites exist, errors/skips are zero. Supports testsuite and testsuites roots. Genuine historical 533/162/11 and 1-RED/1-GREEN enforced; current 572/38/12 and 2-RED/2-GREEN checked separately. Empty/partial/error/skip inputs reject, including genuine pytest setup-error and skipped-run XML created by rejection tests. |

The current PDF control helper also needed the continuation's explicit
`reorder_after=True` argument. The first genuine replay failed with TypeError;
`failed-control.log` and its command receipt are preserved. Corrected replay and
a real-PDF harness regression pass; the failed run is never presented as PASS.

## Actual current results and limits

- Full normal pytest with coverage: **572 passed**, zero failures/errors/skips,
  **91.11%** with unchanged **80%** floor. No test exclusions or weakened checks.
- Focused new controls: **38 passed**. Current required section file: **12 passed**.
- Header-parser disconnection: **2 named assertion failures**, exact restoration,
  **2 passes**, unchanged test hash. Genuine XML/logs/argv in `mutation/`.
- Actual offline PDF control, legal ingest/claims/fact-map replay, historical BASE
  probe and current navigation observation reproduced. Navigation's `mirror_root`
  error remains an audit observation for human review; no production repair/issue.
- Ruff and Black pass on all evidence scripts and new controls. Strict verifier
  mypy passes. Whole-production mypy reports **two unused-ignore errors** in
  unchanged `src/doc_lineage/adapters/docling_segmenter.py:111-112`; retained in
  `type-production.log`. Production bytes match the expected starting revision.
- Python 3.12 Anaconda system-site-packages isolated venv; local editable install,
  no shared-runtime install. Actual tool versions are in `environment.json`;
  exact dev-pin behavior is UNKNOWN. Two inherited pandas warnings remain.
- Fourteen observed native Docxodus executions across the first and final full
  runs exited 0, each checked before invocation against binary SHA-256
  `12b0955111e348543e55ac9fbc06599b3e79294781198c6fb1b46f3029867c36`.
  Exact argv/paths/results in `native.jsonl`; the venv-only observer is retained.
  Installed archive hash matched the parent's prior explanation. Publisher
  UNKNOWN (prior ad-hoc/no-TeamID evidence); no OS prompt observed, no helper
  download/privacy change/Office/private corpus. These local calls do not prove
  hosted/provider/sibling acceptance.
- Capability consult used `--surface opener-lane` and actual task words; failed
  on sandbox-denied shared registry lock. Error retained; fail-open, no returned
  offers or capability execution claimed.

Recovery bytes are copied from actual raw captures. Only trailing horizontal
whitespace in the new disconnected log/XML is normalized for Git diff hygiene;
actual cases/outcomes/timings are unchanged. `raw-to-public.json` binds raw and
public hashes and records these two transformations. Original raw captures and
the initial diff-check failure remain external. All other copies are unchanged. All command receipts bind argv, logs and source
inputs. The current checksum index includes new receipts/scripts and every
bundled artifact. Historical XML and receipt bytes are preserved. Current
`source-bindings.json` is separate metadata, not a fabricated historical refresh.
The original verifier at the starting head rejected the historical test binding
because that file had changed; the explicit historical/current split repairs
that diagnostic without claiming the old runs exercised current test bytes.

Ownership evidence preserves both all-head reservations/completions and direct
terminal native attempts 39032882200:1 / 39033715589:1. Parent claim and pause
remain in place. A fresh all-comments/native-attempt gate is required immediately
before push. No CI waiting, provider verdict, merge or closure is claimed.
