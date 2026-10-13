# Document-identity audit evidence

Inspected source: `33cd32ff1e41350d293734b0d16b327cb54c3652`.
Report: `docs/reports/document-identity-conformance-audit.md` (#94).
New independently reproduced instance: #95, invalid lineage content hashes.
Known page emission defect stays with #86/#87. No production repair is bundled.

Run from the repository root with its local Python environment:

```sh
python3 -m pytest tests/emit/test_evidence_object.py tests/test_identity_manifest.py tests/lineage/test_supersession_chain.py -q
python3 -m pytest tests/emit/test_evidence_object.py tests/test_identity.py tests/test_identity_manifest.py tests/lineage tests/ingest/test_ingest_synthetic_pdf.py tests/test_extract_coverage.py tests/render tests/export/test_docx_redline.py tests/export/test_fact_key_map.py tests/export/test_fact_key_map_cli.py tests/harvest/test_edgar_ex10_offline.py tests/test_schema_wire_names.py -q
PYTHONPATH=src python3 docs/evidence/document-identity-audit/probe_contracts.py
PYTHONPATH=src python3 docs/evidence/document-identity-audit/probe_contracts.py --require-hash-conformance
python3 docs/evidence/document-identity-audit/check_inventory.py
```

The two suites report 71 and 242 passing tests, zero skipped. The broader
suite has two environment-version warnings. `hash-conformance-red.log` is an
expected failure on inspected production behavior, not a repaired/regression
GREEN claim. The default probe records both defects plus valid-hash and
filename-only controls. A future hash fix must add the named pytest regression
in #95; this observation script does not substitute for that implementation.

Inventory evidence proves all 23 required source matches occur once in the
report. A removed row is rejected; byte-identical restoration passes. This
checks inventory completeness, not the semantic classifications by itself.
The scripts are snapshot probes; check out the inspected source revision to
reproduce them after later production changes.

`proof-bindings.json` contains SHA256/byte bindings for every published proof
file except itself, and all inspected source files plus the convention/schema.
Published logs redact only local interpreter/account/checkout paths; outcomes
are unchanged. Raw run output remains in the private automation receipt.
Native apps, live SEC/Docling/provider behavior and hosted CI are UNKNOWN.
