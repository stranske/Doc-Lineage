# PR #130 same-branch main integration

This is the bounded source #113 audit/harness continuation from
`c27168e94364d52ec681d3b3827281118d46a8ba`, integrating main
`c274b866e695d92a083c182c19f3119cab01e0b0` with a two-parent merge
`67c4e20281843c8f869be2fcbb9409a468eefe6a`. Both payloads and their Git ancestry
are retained. No production/schema/workflow changes were made beyond incoming
main; H1/H2 remain report-only. No new issue/branch/PR, acceptance-scope change,
merge/closure, hosted dispatch, Brain write, credential change or Office call.

## Binding semantics

Actual executions bind the full source/test/fixture/schema/vocabulary/build-config
and evidence-helper input inventory (148 files) to immutable Git
revision **`fadb1b05fc5849aff145a53d2a542dfec1999422`**, committed before capture. The final evidence-only
commit can have a different HEAD while retaining exactly these inputs. Every
command receipt captures actual argv, exit, log hash, revision, input hashes and
post-execution input identity. The full run has no exclusions and uses normal
repository test discovery and the unchanged 80% coverage floor.

`../issue-113/verify_evidence.py` defaults to **archive verification**: exact
checksum inventories, immutable Git bindings, actual JUnit cases/outcomes,
persisted-artifact hashes and mutation restoration. Original proof is bound to
`a9e5ce23c4295a1948f6f7bd58ea50fcddd67521`; recovery proof and its unchanged 144
`current_inputs` entries are bound to immutable `c27168e…`. Those old field names
are historical metadata, not a claim of current coverage. A future producer/test
change is reported as current-input drift and does not corrupt valid old XML.
An incorrect archived source hash still fails closed against the immutable Git
object. Both historical full runs (533 and 572), and their 1-case/2-case causal
RED/GREEN components, remain distinct from this capture.

Run with an explicit interpreter, for example:

```sh
/opt/anaconda3/bin/python3 docs/evidence/issue-113/verify_evidence.py
/opt/anaconda3/bin/python3 docs/evidence/issue-113/verify_evidence.py --require-current
```

`--require-current` adds strict **current admission**: fresh integration proof must
exist, its complete immutable input inventory must verify, and every current
input plus the current inventory must match it. Default archive PASS is never
current-head qualification. `current_admission=MATCH` reports input identity;
current admission does not establish provider/CI/sibling/source acceptance.
The six added harness cases use real Git objects to distinguish producer/test
and missing-file drift from corrupt archived hashes, and reject absent fresh
proof. The separately executed `admission-control.json` records default archive
PASS / strict current FAIL under actual temporary producer drift, exact restored
current PASS, and rejection of an intentionally corrupt copied integration binding
even after recomputing its checksums. Genuine proof and tests stay unchanged.

## Actual results

- Normal full suite: **613 passed**, zero failures/errors/skips;
  **90.64%** coverage with the unchanged 80% floor.
- Harness controls: **44 passed** (the original 38 plus six
  binding/admission cases). Required section file: **12 passed**.
- Actual PDF/header-parser disconnection: **2 named assertion failures**, exact
  production restoration, unchanged tests, then **2 restored passes**. Incoming
  blackline source hash is `d99738ce7c1975b4450c88731cb0773f101f5786bec884fae57f5368f72f5270`;
  old `c339…` recovery proof was not relabeled as this execution.
- PDF pairing control and three-process ingest/claims/fact-map legal replay pass.
  Navigation replay records the existing `mirror_root` H2 mismatch; it is an audit
  observation, never a production fix or claimed navigation success.
- Ruff, Black, strict verifier mypy and focused blackline/CLI mypy pass. Full
  production mypy still reports exactly two baseline unused-ignore errors at
  `adapters/docling_segmenter.py:111-112`. That source is unchanged from both
  incoming main and the recovery head; the failure remains in its own receipt.

## Environment, failed attempt and preservation

Python 3.12.2 from Anaconda, isolated system-site-packages venv and offline local
editable install; no shared environment mutation. Actual package versions are in
`environment.json`; exact dev-pin equivalence is UNKNOWN. Two inherited pandas
warnings remain. The first genuine full run was **612 passed / 1 failed** in the
console editable-install test: I omitted the previous recovery's
`PIP_NO_BUILD_ISOLATION=0` environment setting. The reproduced installer error
could not resolve build-isolated setuptools while `PIP_NO_INDEX=1`. Both that
failure and the successful local no-build-isolation installation are retained;
the complete normal suite was then rerun without test/threshold changes. The
first failed XML is in `first-full-attempt/full.xml.gz`, not counted as passing
proof. Failed-attempt log/XML/installer stderr are gzip-compressed without byte
changes; decompress to check the original command log SHA-256.

Across both full attempts, **30 actual native executions** were
observed, all exit 0, with exact executable paths/argv/SHA-256 and outcomes in
`native.jsonl`. The installed Docxodus 1.0.0 archive matches previously explained
SHA-256 `c231bd1aefa7af56932cf0aebbd7a0fbe8cf1143eb3baff6abf42dc426c04571`.
The venv-only observer verifies helper SHA-256
`12b0955111e348543e55ac9fbc06599b3e79294781198c6fb1b46f3029867c36` before each
launch. Publisher remains UNKNOWN (prior ad-hoc/no TeamIdentifier). No new
helper download, Office execution, privacy bypass or unexpected OS prompt was
observed. These synthetic local executions do not establish private-corpus or
hosted acceptance.

The required capability consult used `--surface opener-lane` and the actual task
words. Sandbox denial of the shared registry lock is retained, fail-open; no
offers were returned, no declines invented, and no capabilities executed.

`preserved-history.json` records byte-for-byte checks of all old evidence files.
Only the verifier and its checksum-index entry changed; their before/after hashes
and the previous checksum index are retained separately. Original XML, source
bindings, receipts, helper scripts and mutation bytes were preserved. New copies
match raw captures after documented gzip decompression except trailing horizontal whitespace stripped from the new
causal RED log/XML for Git hygiene; `raw-to-public.json` binds both forms and
names transformations. Cases, outcomes and timings are unchanged. Raw captures
remain in the managed measurement directory.

`preflight/` retains all-page PR/source comments, decoded all-head reservations
and direct attempt/job observations. All three reservations have completed
receipts; actual implementation children are terminal. The fresh prepush gate
and remote readback are retained externally with the final parent handoff entry.
Parent-owned source guardian/pause and dispatcher ownership remain untouched.
No CI wait or provider PASS is claimed for the new combined head. Normal
independent review and exact-head acceptance remain the parent's next action.
