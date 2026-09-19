# Fact-key map export

Export identity joins from a JSON array of tracked-variable records:

```bash
doc-lineage export-fact-key-map tracked-variables.json --output fact-map-run
```

The output directory must be new. The exporter writes `fact_key_map.json` and
`artifact-manifest.json`; the manifest names the artifact
`artifact:fact_key_map.json`, uses the existing `data` kind, and records the
actual file's SHA-256 and size. Existing ingest runs are never overwritten.

The map is keyed by `variable_id`. Each entry preserves the exact `ontology_key`
and canonical `entity_ref`, plus `period` when supplied. A Mosaic consumer joins
its `fact_key` to `ontology_key` within the same entity and period; matching
ontology keys alone must not conflate different managers or reporting periods.
No ontology aliases or display names are substituted.

Every input row must declare `tracked-variable/v1` and provide all three identity
fields. Empty inputs, malformed identities, and duplicate variable IDs carrying
different mappings fail before creating output. Identical repeated mappings are
deduplicated. Output ordering and hashes are deterministic.

This exporter validates the identity projection only. Upstream extractors remain
responsible for evidence and provenance validation; it does not fabricate tracked
variables from raw ingest segments. The test fixture is a minimal identity
projection, not a complete evidence-bearing tracked-variable example.

Validation:

```bash
python -m pytest tests/export/test_fact_key_map.py tests/export/test_fact_key_map_cli.py -q -o addopts=
```

Deliberate-break gate: remove `entity_ref` from the first entry in
`tests/fixtures/fact_key_map/tracked_variables.json`; run
`python -m pytest tests/export/test_fact_key_map.py::test_map_joins_on_ontology_key -q -o addopts=`.
It must fail. Restore the fixture and rerun; it must pass.
