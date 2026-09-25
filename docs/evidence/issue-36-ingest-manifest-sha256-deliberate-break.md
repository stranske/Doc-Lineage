# Deliberate-break evidence: ingest manifest segments `sha256` gate (#36 / #8)

Linked issue: `stranske/Doc-Lineage#36` (parent gate `#8`).

## Mutation (temporary, reverted before merge)

In `src/doc_lineage/ingest.py`, the segments artifact entry temporarily used a constant hash instead of `sha256_bytes(segments_bytes)`:

```python
"sha256": "0" * 64,  # deliberate-break: skip real artifact sha256
```

Production code on this branch keeps the real computation; this file records the RED/GREEN transcript only.

## RED — `pytest tests/ingest/test_ingest_synthetic_pdf.py::test_ingest_writes_valid_manifest -q`

```
FAILED tests/ingest/test_ingest_synthetic_pdf.py::test_ingest_writes_valid_manifest
>       assert artifact["sha256"] == _sha256(segments_path)
E       AssertionError: assert '000000000000...0000000000000' == 'c47b12a3b3a0...3371085470521'
============================== 1 failed in 3.83s ===============================
```

## GREEN — same command after revert

```
tests/ingest/test_ingest_synthetic_pdf.py .                              [100%]
============================== 1 passed in 6.60s ===============================
```

## Verification command (this PR)

`pytest tests/ingest/test_ingest_synthetic_pdf.py::test_ingest_writes_valid_manifest -q`
