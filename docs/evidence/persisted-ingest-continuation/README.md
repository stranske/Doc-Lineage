# Persisted ingest audit continuation — 2026-10-17

Base: `a9e5ce2` (the prior #113 audit, containing the #128 implementation).
This continuation enumerates all eleven bounded inventory entries in README and
extends the existing real-PDF regression with reversed section/page order. The
fresh process still receives only persisted segment paths. Assertions check IDs,
pairing methods, the changed fee and unchanged term, membership on both sides,
and the fee's actual evidence source/page as it moves from page 1 to page 2.
Production code, schemas and workflows retain their original bytes. No missing
production transition is repaired by this audit.

## Verified task checklist

- [x] Enumerate section comparison, tracked-variable production and directly
  documented sibling handoffs in [README](../../../README.md#persisted-ingest-consumer-audit):
  all I1–I11 entries, including intentional boundaries and unknown adoption.
- [x] Trace producer artifacts, production callers, identity validation and
  restart evidence: the [full inventory](../../reports/persisted-ingest-consumer-audit.md#complete-bounded-inventory)
  records the contracts and source/test evidence; current controls rerun below.
- [x] Link existing [legal extraction #111](https://github.com/stranske/Doc-Lineage/issues/111)
  and [persisted pairing #112](https://github.com/stranske/Doc-Lineage/issues/112)
  work. H1/H2/H3 remain findings for human review without issue filing or repairs.
- [x] Demonstrate bounded missing-transition checks and working controls: retain
  revision-bound historical probes, rerun the actual legal/navigation path, and
  strengthen the section-pairing restart control. Native DOCX-package replay and
  general CLI/architecture changes remain excluded.

## Verified acceptance checklist

- [x] Every entry in the bounded seam records contract, producer/consumer,
  source/test evidence and confirmed, intentional or unknown disposition in the
  linked full inventory; README now enumerates the complete set directly.
- [x] Classified gaps have traced paths and bounded probes in the prior audit;
  working controls include the newly strengthened section regression and the
  current legal extraction/fact-map replay. Historical absence probes are not
  promoted into tests requiring repaired functionality to stay missing.
- [x] Known instances link to existing owned work; additional findings are
  returned for human review. No issues or pull requests were created/changed.
- [x] Exact required command, `python -m pytest tests/blackline/test_section_id_pairing.py -q`:
  **12 collected, 12 passed**, exit 0; actual output in [exact.log](exact.log).
- [x] Deliberate-break gate: temporarily disconnect the existing scoped
  `_parse_section_header(segment.text)` call in `src/doc_lineage/blackline.py`.
  Both `same-order` and the added `reordered-sections` case fail with
  `PERSISTED_INGEST_PAIRING_DISCONNECTED` (**2 failed**, exit 1). Restore exact
  bytes and run the unchanged regression: **2 passed**, exit 0. This demonstrates
  the existing production boundary, not a new production repair.

## Actual commands and results

The existing mutation helper was run as:

```sh
PYTHONPATH=src python docs/evidence/issue-113/deliberate_break.py /tmp/doc-lineage-113-continuation-mutation
```

[mutation.json](mutation.json) records exact child commands, exit codes and hashes;
[disconnected.log](disconnected.log) and [restored.log](restored.log) retain actual
output; trailing horizontal whitespace in the disconnected log is stripped for
the diff gate, without removing lines. The helper restores production in `finally` and checks
test bytes remain unchanged. Original/restored production SHA-256:
`c339f553462d1437ee512e07ef5a20a401779dedf703c904534b3003f907afd7`.
Regression SHA-256:
`bba39e27af9887646742a855e9cd1e4f7f5cc03f75db38cc73188b05ce3f018a`.
The unchanged mutation helper selects only this non-slow regression. The broader
test command explicitly excludes slow tests:

```sh
python -m pytest tests/blackline tests/mutations tests/ingest/test_variables_provenance.py tests/emit tests/export/test_fact_key_map.py tests/export/test_fact_key_map_cli.py tests/render tests/test_cli.py tests/compare -q -m 'not slow'
```

Result: **167 passed**, 18 existing Python 3.14 deprecation warnings; actual
output in [related.log](related.log).

```sh
PYTHONPATH=src python docs/evidence/issue-113/replay_legal.py /tmp/doc-lineage-113-continuation-legal
PYTHONPATH=src python docs/evidence/issue-113/probe_current.py /tmp/doc-lineage-113-continuation-legal/claims
```

The first command passes source/claim/evidence/manifest/map binding assertions;
[legal-commands.json](legal-commands.json) retains all three fresh CLI subprocess
commands and results. The second records the actual produced claim's navigation
failure, `mirror_root must be a relative POSIX path without traversal`, with input
hashes and provenance in [navigation.json](navigation.json). This is H2, returned
for human decision. No live sibling adoption or linked-PR state is asserted.

`python -m pytest tests/ -q -m 'not slow'` also ran: **520 passed, 14 failed**.
Thirteen failures exercise OCR with `pypdfium2` unavailable in this environment;
the remaining failure is the existing editable-install subprocess test, whose
root cause was not isolated. These source/test files are unchanged. No full-suite
success is claimed, and no test was disabled or assertion weakened.

Black formatted the changed Python test at line length 100. The exact repository
gate then passed with environment settings for one worker and a writable cache:

```sh
BLACK_NUM_WORKERS=1 BLACK_CACHE_DIR=/tmp/doc-lineage-black-cache black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
ruff check tests/blackline/test_section_id_pairing.py
git diff --check
```

Black reports **167 files unchanged**. The initial default multiprocessing run
failed on sandbox socket restrictions; single-worker checking completed all
files but stalled until a timeout woke its event loop. The final cached check
exited 0 normally. Ruff and diff checks pass. Runtime: Python 3.14.8, pytest 9.1.1.
The original #113 evidence remains a historical receipt bound to its original
regression bytes; use this receipt for the extended regression's hash/results.

The workspace's `.git` directory is read-only: staging here fails to create
`index.lock`. The scoped files are committed in an isolated, local shared clone
at `/tmp/doc-lineage-ingest-audit-commit`, with no workflow files checked out.
`/tmp/doc-lineage-ingest-audit.bundle` carries that commit and its parent history
for transfer. The workspace branch itself is unchanged.
