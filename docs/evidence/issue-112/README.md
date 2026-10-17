# Issue #112 delivery proof

Scope: local **extracted-PDF section pairing**, not classified text differences,
semantic supersession, PDF-to-DOCX conversion or native DOCX replay acceptance.
Source #112 stays open; no merge or hosted/provider/Office acceptance is asserted.

The exact source/test/fixture hashes and command receipts are in
`delivery-receipt.json` and `evidence-bindings.json`. The synthetic PDFs under
`fixtures/` are actual ReportLab PDFs with distinct original-byte hashes.
`run/` retains the two real ingests, content-addressed original snapshots,
manifested segments/evidence, and the immutable comparison artifact. The input
PDFs were removed from the working replay directory after ingest, so comparison
and lookup use only persisted runs. `run/argv-results.json` captures each
independent command process, return code, stdout and stderr.

Portable verification from a checkout (use the selected repository venv or
`/opt/anaconda3/bin/python3`; destination must not already exist):

```bash
PYTHONPATH=src /opt/anaconda3/bin/python3 docs/evidence/issue-112/replay.py /tmp/issue-112-replay
```

`named-exact.log` records the mandated command with nonzero collection:
`/opt/anaconda3/bin/python3 -m pytest tests/blackline/test_section_id_pairing.py -q`.
`focused-cli.log` covers the new subprocess integration and existing CLI.
The full suite retains the configured branch coverage and 80% floor. The initial
shared-runtime run and isolated rerun are retained separately, including their
actual XML; no test exclusions, collection edits or coverage-floor reductions.
The isolated environment inherits installed packages and installs this checkout
locally. `PIP_NO_BUILD_ISOLATION=0 PIP_NO_DEPS=1` prevents the existing editable
install test from installing into the shared interpreter or resolving unrelated
dependencies. These settings do not alter the implementation or test assertions.

`mutation-red.xml` is a genuine failed-test JUnit capture: the production
`_section_comparison` call to `align_sections` was replaced with an empty list.
The unchanged named regression failed its
`PERSISTED_SECTION_PAIRING_MUST_CALL_EXISTING_ENGINE` assertion. The production
file was restored byte-for-byte, then the same regression passed in
`mutation-restored-green.xml`. `production-mutation.patch` and
`mutation-receipt.json` bind original/mutated/restored production hashes and
unchanged test hashes. This is an actual production mutation, not a mock or a
test-only expected-failure demonstration.

Public logs/JSON/XML are normalized copies of external raw captures: checkout,
home, temporary validation and virtual-environment paths become `$REPO`, `~`,
`$RUNTIME_TMP`, `$RAW` and `$VENV`; any XML hostname is redacted. JUnit test cases,
assertion failures, counts and coverage measurements are retained. Raw and
normalized hashes are paired in `evidence-bindings.json`. Actual synthetic PDF,
manifest, segment and comparison bytes in `run/` are unmodified. These logs and
hashes are local evidence, not cryptographic attestation or a provider verdict.

The capability advisor was invoked before validation with the actual
implementation description. It exited 1 because opening its registry lock was
denied by this task sandbox. `advisor.argv.json`, `advisor.stderr` and
`advisor.exit` preserve the unavailable result. It returned no considered
capabilities, declines or triggers; none are claimed used/useful. The run
continued under the requested fail-open rule. Git remote synchronization was
used; no delegation, native helper, workflow writer, scheduling/model change or
source agent label was introduced.

`writer-terminal-receipt.json` records the final all-head reservation/completion
refresh and direct recorded workflow-attempt/job inspection, including main
branch runs. Prior source #110/#111 writers were inspected read-only and their
branches/worktrees were not changed. Target #112 ownership is reported
separately from their status.
