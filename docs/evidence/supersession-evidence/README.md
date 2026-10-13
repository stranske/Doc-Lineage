# Supersession publication proof

Original main `ad55027827bff033d637bd8171f200e2e60a2d3f` with the rewritten prefix-only regressions: **14 failed / 43 passed**. The regressions expose filename-only publication and the missing unconfirmed-hint field.

Final focused gate: `python3 -m pytest tests/test_identity_manifest.py tests/lineage/test_supersession_chain.py tests/lineage/test_supersession_evidence.py -q --junitxml=docs/evidence/supersession-evidence/focused.xml` -> **91 passed, zero skipped**.

Full gate: `python3 -m pytest --cov=doc_lineage --cov-report=term-missing --junitxml=docs/evidence/supersession-evidence/full.xml` -> **384 passed, zero skipped**, **91.28%** coverage against the unchanged 80% floor. Two pre-existing dependency deprecation warnings remain in the log.

Deliberate production breaks (commands and exact restoration SHA-256 in `mutations.json`):

- Manifest: replace evidence-gated `supersedes` assignment with filename-derived predecessor hints. Both named prefix-only regressions fail (**2 failed**); exact restoration yields **2 passed**.
- Lineage: temporarily restore the original filename-only publisher. The named chain regression fails (**1 failed**); exact restoration yields **1 passed**.
- Shared validator: stop rejecting blank evidence detail. Both publication paths detect empty/whitespace detail admission (**4 failed / 14 passed**); exact restoration yields **18 passed**.

Positive tests exercise all three mechanisms, serialized manifest links and actual edge output. Additional regressions reject missing/unknown mechanisms, non-string/empty detail, unavailable content, self-links, conflicting predecessors and cycles; confirm explicit evidence overrides filename order/rename hints; preserve evidence after caller mutation; and prove incremental scans cannot silently reuse old confirmed lineage. Evidence is caller-supplied: these tests do not establish that an owner assertion or comparison is factually correct.

Ruff/Black and whitespace checks pass on touched files. Local mypy reports two unchanged optional Docling `unused-ignore` diagnostics at adapter lines110/111; with only that diagnostic disabled locally, all three changed source modules pass. No typing policy, dependency, shared contract, workflow or identity algorithm is changed.

Logs/JUnit retain outcomes and source excerpts with local usernames, hostnames and temporary paths redacted. `source-bindings.json` binds final source/tests; `sha256.json` binds the published proof files. Raw local originals are retained outside the repository. Hosted CI, provider verifier PASS, and native-app acceptance are UNKNOWN until their own checks run.
