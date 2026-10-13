# Issue 95: confirmed-lineage content ID validation

Inspected base: `fd14b888` (merged document identity audit). The fix validates all supplied lineage records and both claim endpoints as exactly 64 lowercase ASCII hexadecimal characters before publication. It retains explicit evidence, deterministic ordering, duplicate-byte identity and filename-only suppression. Digest syntax does not establish original-byte provenance.

## Replay

```bash
python3 -m pytest tests/lineage/test_supersession_evidence.py tests/lineage/test_supersession_chain.py tests/test_identity_manifest.py -q
python3 -m pytest tests/ -q --cov=src --cov-report=term-missing
```

- Acceptance: 132 passed, zero skipped.
- Full suite: 429 passed, zero skipped, two environment warnings; 91.32% coverage, 80% required.
- New regression suite against original production source: 37 failed, 38 passed. Existing empty/whitespace claimed IDs were already rejected; the remaining failures prove the wider publication gap and missing digest-specific admission.
- Deliberate break: replace only `_validate_content_hash`'s condition/raise body with `return None`. The named `test_malformed_content_hashes_rejected` has 36 failures. Restore the exact bytes: 36 pass. `mutation.json` binds corrected/bypassed/restored SHA256 values.
- `source-bindings.json` binds final production and regression test bytes. `SHA256SUMS` binds published proof files.
- Ruff, full Black and whitespace checks pass. Focused mypy passes with unused-ignore diagnostics disabled for unchanged imported optional Docling adapter annotations; repository type policy is unchanged.

Logs retain command outcomes; local workspace/account metadata is redacted. All inputs are synthetic. Hosted CI, native application behavior and post-merge provider acceptance remain unverified by these local results.
