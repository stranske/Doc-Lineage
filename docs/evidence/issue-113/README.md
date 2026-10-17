# Issue 113 audit evidence

[Audit and complete inventory](../../reports/persisted-ingest-consumer-audit.md).
Initial main: `45971929b534d953e1c56ffb42b4bdfc3fd4b994`.
Final reviewed main/base: `aa2351f72636e76f80b4e0013e9a099b2d9a495b` after #128 merged.
Production, schemas and workflows have no audit changes. Final `src` Git tree
and every source/test/fixture binding are in `source-hashes.json`; each captured
command also retains its own source/test/fixture map. The new test's SHA-256 is
`d096a7810d1b5435effe5bd0469b79c66ce9ae22ebeea3d67399425078d3b3c2` throughout
actual RED/GREEN and final-base execution.

## Actual validation

| Scope | Genuine command/result |
| --- | --- |
| Exact required command, final base | `$VENV/bin/python -m pytest tests/blackline/test_section_id_pairing.py -q` — **11 collected, 11 passed**, `final-exact.log` and matching argv/bindings JSON. Initial-base exact/focused results retained separately. |
| Related seam checks, initial base | `python -m pytest tests/blackline tests/mutations tests/ingest/test_ingest_synthetic_pdf.py tests/emit tests/export/test_fact_key_map.py tests/export/test_fact_key_map_cli.py tests/render tests/test_cli.py tests/compare -q --junitxml=$RAW/related.xml` — **162 passed**, `related.log/xml/json`. |
| Full suite, initial base | `python -m pytest --cov=src --cov-report=term-missing --cov-report=xml:$RAW/coverage.xml --junitxml=$RAW/full.xml` — **479 passed, 91.07%**. Historical, not the final-base result. |
| Full suite, final base | Same full command with `final-coverage.xml` / `final-full.xml` — **533 passed, zero failures/errors/skips, 91.11%**. Required 80% floor and existing exclusions unchanged. Editable-install, wheel/source archive and actual CLI tests ran unmodified in the isolated venv. |
| Final production disconnection | `python docs/evidence/issue-113/deliberate_break.py $RAW/final-mutation` invokes the unchanged named test twice: **1 assertion failure** containing `PERSISTED_INGEST_PAIRING_DISCONNECTED`, then exact-byte restoration and **1 passed**. Genuine inner logs/XML, exact argv, production/test hashes and mutation recipe are in `final-mutation/`. Initial-base mutation evidence is also retained. |
| Real PDF replay control | `python docs/evidence/issue-113/replay_control.py $RAW/final-control` passes the unchanged regression, retaining two real PDFs, manifests, segments, evidence, actual edge NDJSON and replay summary. IDs 1/2; fee changed, term unchanged; `gate_provision_change`. |
| Current legal handoff | `python docs/evidence/issue-113/replay_legal.py $RAW/current-legal` — actual original synthetic PDF → persisted ingest → source-derived claims/evidence/source copy → fact-map, using **three fresh public CLI processes**. Validated schema, 1.75/1.25 rates, digest, page, evidence reference, identity join and every artifact hash/size. No authored-claim fixture substituted. `current-legal/commands.json` has child argv/results. |
| Bounded missing-transition probes | `probe_base.py` on initial main records actual path-to-builder failure, public pairing/extraction dispatch failures, segments-to-fact-map rejection, raw-evidence-to-navigation rejection, forged caller identity acceptance and original PDF header/fee detection limitation. Outcome records are observations, not tests enforcing future absence. |
| Additional current gap | `python docs/evidence/issue-113/probe_current.py $RAW/current-legal/claims` passes the **actual produced claim** into `resolve_triple_link`; it records the `mirror_root: "."` rejection, exact producer/consumer/contract and claim/evidence hashes. `current-navigation.log/json`. No bundled repair or issue filing. |
| Static checks | Changed test and all six evidence scripts: Ruff and Black check pass (`final-evidence-lint`, `final-evidence-format`). `git diff --check` passes. No production change requires claiming a new full-mypy result. |

The full and related suites retained two inherited pandas warnings for installed
numexpr/bottleneck versions. Runtime is Python 3.12.2. The venv was created with
`/opt/anaconda3/bin/python3 -m venv --system-site-packages /tmp/doc-lineage-113-venv`;
packages are inherited for reading, while editable installation and console
scripts belong to that venv. Child commands used that venv first on PATH,
`PYTHONPATH=$REPO/src`, `PIP_NO_BUILD_ISOLATION=0`, `PIP_NO_DEPS=1`, and a raw-directory
coverage file. No shared-interpreter install occurred. Installed setuptools
83.0.0, Ruff 0.16.7, Black 26.5.1, mypy 2.3.1 and reportlab 5.0.1 differ from repo
dev pins; exact pinned-version behavior remains **UNKNOWN**. `environment.json`
records actual versions. No assertions, coverage settings or test exclusions were
weakened. This suite is local evidence, not provider/hosted acceptance.

## Portable replay and independent mutation reconstruction

Set `REPO` to a disposable checkout containing this delivery, `VENV` to a Python
3.12 environment with the recorded dependencies, and `RAW` to a new directory
outside the checkout. The Python helpers require `PYTHONPATH="$REPO/src"`.
Run from `$REPO`; published argv/log placeholders are data, not shell-expanded
commands. `$BASE_RUNTIME`, `$TASK_TMP`, `$ADVISOR_SOURCE`, `$ORCHESTRATOR` and
`$USER_ROOT` replace machine-specific environment paths. XML hostname is `HOST`.

```sh
"$VENV/bin/python" -m pytest tests/blackline/test_section_id_pairing.py -q
"$VENV/bin/python" docs/evidence/issue-113/replay_control.py "$RAW/control"
"$VENV/bin/python" docs/evidence/issue-113/replay_legal.py "$RAW/legal"
"$VENV/bin/python" docs/evidence/issue-113/probe_current.py "$RAW/legal/claims"
"$VENV/bin/python" docs/evidence/issue-113/deliberate_break.py "$RAW/mutation"
```

The mutation script checks exactly one occurrence of
`        parsed = _parse_section_header(segment.text)` and replaces it with
`        parsed = None  # ISSUE113_TEMPORARY_PRODUCTION_DISCONNECTION` in
`src/doc_lineage/blackline.py`. It executes the unchanged named new regression,
restores exact bytes in `finally`, verifies test identity and reruns. Expected
production SHA-256 is `c339f553462d1437ee512e07ef5a20a401779dedf703c904534b3003f907afd7`,
mutated `1174e49079b382b57ecd19499778eece27a42e763d455d3c8028bf8ee05435af`, restored
identical to original. It must observe an assertion RED and restored GREEN;
this is a control of an existing boundary, not a production repair. Do not run
simultaneous source mutations in that disposable checkout.

To independently reconstruct initial-base missing-transition observations, make
a disposable checkout of `45971929b534d953e1c56ffb42b4bdfc3fd4b994`, copy this
`probe_base.py` under `docs/evidence/issue-113/`, and run it with `PYTHONPATH=src`
and a new output directory outside that checkout. It rejects a changed production
tree. This explicit historical replay avoids tests that would fail merely because
#128/#129 subsequently repair an owned gap. That helper performs no network,
CLI offload, native Office or OCR launch.

Run `python docs/evidence/issue-113/verify_evidence.py` to verify the evidence
checksums, bound source/test/fixture bytes, real XML counts, exact restoration
and persisted artifact hashes/sizes. `SHA256SUMS` covers all committed evidence
bytes other than itself. PDF files are
genuine, synthetic and copied byte-for-byte from the actual executions. Ingest
manifests bind original segment/evidence bytes; no normalized source content or
hash values were altered. `normalization.json` binds genuine raw originals to
public copies by SHA-256 and records whether normalization occurred. XML retains
real cases, outcomes, failure messages and timing. Trailing horizontal whitespace
in text transcripts/XML is normalized without removing line breaks. Genuine PDF
bytes are unchanged and marked binary by evidence-local `.gitattributes`. The
first staged diff-check failure on generated whitespace/PDF text detection is
preserved in raw evidence; final diff-check passes after this normalization. No fabricated JUnit or manually
assembled passing test report is used. Raw originals are outside checkout at
`/tmp/doc-lineage-113-raw`.

## Ownership, advisor and publication boundaries

`writer-gate.json` records all 81 earlier PR heads, 1,013 full issue/PR comments,
inline comment coverage, **57 decoded reservation/completion records**, and direct
inspection of **all 29 recorded workflow attempts**, including main
`workflow_dispatch` attempts. No source-113 prior reservation/completion/attempt
was found; its original dispatcher claim is expected and remains held. At the
snapshot, PR129 has an unmatched pending reservation; a completed parent attempt
does not prove admitted child terminality. Its existing owner/branch/worktree are
preserved. No new hosted dispatch, second writer or claim release was performed.
PR127 remains separate. PR128 merged through its existing owner during this run;
this audit neither merged it nor closed its source. Refresh gates before any later
merge/acceptance action.

Mandatory `handoff.sh check-linked stranske/Doc-Lineage#113` returned FREE before
work and before publication, through the detached network wrapper. Full live
source/linked-PR comments were refreshed, and available-label/cap receipts checked.
The fresh scoped cap helper reports 2 existing opener-owned PRs and no cap reached;
one audit PR is authorized. Fetch updated main but pruning a deleted branch was
sandbox-denied on `packed-refs.lock`; explicit `fetch origin --no-prune` refreshes
without that blocked mutation. No other worktree or in-repo lane state was touched.

The configured substantive seat is Sol (`gpt-6.1-sol`); no model, cadence or
scheduler changes were made. The exact required capability-advisor consultation
was attempted before validation with the actual task description. It failed on
the shared registry's sandbox-denied lock (`advisor-error.log`); proceeded
fail-open. No successful heartbeat, returned trigger, recommendation or capability
execution is claimed. Manually considered native/helper/hosted/frontend and
production-repair work were declined as outside the authorized scope. No tool was
launched to provoke a computer-wide prompt. Additional findings are returned only
in the audit report for human decision. No CI wait, merge, source closure or
provider/sibling acceptance is included in this task.

## PR130 evidence harness recovery (expected start e46a58c)

The six review findings are addressed in the evidence harness only. See
[recovery dispositions](recovery/README.md) for exact finding URLs and results.
Original historical logs/XML, mutation receipts and `source-hashes.json` are
unchanged. The original checksum index is retained as
`recovery/original-SHA256SUMS`; the current index covers every evidence file
except the root `SHA256SUMS` itself, including this recovery.

The native continuation parameterized the regression after the original audit:
its current hash is `bba39e27af9887646742a855e9cd1e4f7f5cc03f75db38cc73188b05ce3f018a`.
The original 533/162/11 tests and one-case RED/restored-GREEN are historical
proof at immutable original audit revision
`a9e5ce23c4295a1948f6f7bd58ea50fcddd67521`, not current test counts. The verifier
checks those original bindings using that Git object; a checkout must contain
it. Current recovery inputs and genuine XML have separate bindings in
`recovery/source-bindings.json`. No historical result was rewritten as passing.
