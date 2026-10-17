# Issue #111 local delivery evidence

Implements the bounded management-fee extraction path for
[stranske/Doc-Lineage#111](https://github.com/stranske/Doc-Lineage/issues/111).
Started from remote `main` at `45971929b534d953e1c56ffb42b4bdfc3fd4b994`.
The independent comparison-ID feature is neither included nor required.

- `full-verified.xml` / `.log`: **521 passed, zero failures/errors/skips**;
  **91.11%** combined coverage, unchanged **80%** floor. The Anaconda-based
  `/tmp` venv runs the existing editable-install test without modification.
- `focused-final.xml`: **42 passed**, 53 deselected by `-k tracked_variable`;
  covers synthetic PDF extraction, changed-fee/ambiguous controls, CLI and corrupt
  provenance. The full suite also executes the actual fact-map consumer test and
  the source-archive tests, including all 28 exported-archive consumer tests.
- `native-acceptance-verified.log` and `native-final-*.json`/`.log`: actual installed
  `doc-lineage` executable argv and results for offline PDF ingest → extraction →
  records/evidence → fact-map, including changed-fee and ambiguous controls.
  The ambiguous run emits an empty records array, unresolved diagnostics and no
  asserted value; fact-map export correctly exits 1 without publication.
- `artifacts/`: actual pipeline output, original control PDFs rendered from the
  original mutation text fixtures, copied original document bytes, original
  evidence, input and output manifests, records and maps. These are outputs,
  never extractor inputs. No tracked-variable fixture is copied into extraction.
- `red.xml` / `.log`: the production `rate = float(token)` in `ingest.py` was
  actually replaced with `rate = 1.75`; the changed-fee test raised the named
  **`AssertionError: MANAGEMENT_RATE_SOURCE_DISCONNECTION`**. `green.xml` passes
  after byte-identical restoration. `mutation.json`, `ingest.green.py.txt` and
  `ingest.red.py.txt` bind the exact source bytes. Tests/fixtures stayed unchanged.
- Ruff/Black pass (`ruff-verified`, `black-verified`). Changed-module mypy passes
  with `--follow-imports=silent`. **Full mypy FAILS** on two unchanged
  `docling_segmenter.py:111-112` unused-ignore errors; retained in
  `mypy-full-final.log`. This is not a claim of a clean full type check.
- `full-shared.xml` / `.log` retains the earlier **517 passes / 2 failures**:
  shared editable installation was permission-denied, and the new consumer test
  exposed the missing synthetic PDF in the source archive. `shared-install-failure.log`
  captures the actual permission error. `MANIFEST.in` now includes that PDF and
  the archive test verifies it. The final isolated full suite above passes both
  tests; neither test was excluded or weakened.
- `environment.json`: actual Python/dependency versions. Ruff **0.16.7**, Black
  **26.5.1**, mypy **2.3.1** and reportlab **5.0.1** differ from repository dev
  pins; results with those exact pins remain **UNKNOWN**. The inherited pandas
  numexpr/bottleneck warnings are retained in full-suite logs.
- `advisor.json` and `advisor-declines.json`: opener-lane consultation and
  considered declines. The shared ledger lock was sandbox-denied. The same
  advisor code consulted a captured registry copy; no shared heartbeat is claimed.
- `ownership-preedit.json` / `ownership-prepush.json`: source comments and all-head
  dedup snapshots. No linked PR, native reservation/completion, or recorded attempt
  existed at those gates; no incumbent was displaced. Source agent labels were
  not applied. Any future native reservation must be decoded across all heads
  and its recorded attempt inspected directly before another writer is admitted.

Each command receipt includes its real argv, return code, timestamp and before/
after source/test/fixture SHA-256 bindings. `source-hashes.json` binds final code,
contracts, tests and source fixtures; `SHA256SUMS` binds this evidence directory.
`normalization.json` maps retained raw hashes to portable copy hashes. Only copies
were normalized: path replacements are explicit, and test outcomes, assertion
text and XML testcase data are preserved. Hashes named `log_sha256` or `junit.sha256`
in receipts refer to raw originals, not to their normalized copies.

Raw originals remain at `/tmp/doc-lineage-111-raw` (temporary local storage);
the interpreter is `/tmp/doc-lineage-111-venv/bin/python`, based on
`/opt/anaconda3/bin/python3`. Capture helper source is retained as `.py.txt` for
inspection; the path placeholders in those copies are not executable commands.
No Office application, helper, cloud/model extraction or workflow source change
is part of this implementation. Local validation does not establish hosted CI,
provider PASS, parent adjudication or source acceptance. Do not merge or close
the source based only on this receipt.

## Portable replay

From a source checkout with development dependencies installed, choose a Python
runtime explicitly and a **new** output directory:

```bash
python docs/evidence/issue-111/replay.py --output /tmp/issue-111-new-replay
```

`replay.py` was itself executed (`replay-verified.json` / `.log`). It runs the
public CLI and verifies actual records, schema validity, source digests, page
locators, evidence references, every artifact hash/size, consumer joins and both
controls. It does not replay stored expected outputs. It makes no hosted calls.
