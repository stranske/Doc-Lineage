# Comparison catalog maintenance

The canonical runtime catalogs are `src/doc_lineage/compare/data/segment_tiers.json`
and `src/doc_lineage/compare/data/segment_classes.json`. Production loaders read
these package resources in both source checkouts and installed wheels. Class-to-tier
policy is the `tier` field in the class catalog; it is not a Python branch table.

The root `data/segment_*.json` files are compatibility mirrors retained for the
source issue's documented paths and deliberate-break acceptance command. Edit the
packaged catalogs first, then refresh the mirrors:

```sh
cp src/doc_lineage/compare/data/segment_tiers.json data/segment_tiers.json
cp src/doc_lineage/compare/data/segment_classes.json data/segment_classes.json
python -m pytest tests/compare/test_segment_classification.py -q -o addopts=
```

The named `test_tier_labels_loaded_from_data_not_branches` checks both mirrors
against the packaged resources, loads the source class mirror through the production
loader, and changes a T2 label in an isolated catalog to verify that classification
uses the data. Changing either mirror without the corresponding runtime catalog
therefore fails the same acceptance test. In particular, removing T3 from the root
`data/segment_tiers.json` fails, even though the runtime correctly prefers packaged
resources. Restore deliberate mutations before committing.

## Recovery acceptance evidence (2026-09-19)

The source issue #5 follow-up to PR #39 was checked against the merged implementation:

| Check | Broken result | Restored result |
| --- | --- | --- |
| Existing root class mirror lacks runtime `tier` mappings | Named catalog test fails | Named catalog test passes after mirror refresh |
| Remove T3 from root `data/segment_tiers.json` | Named catalog test fails | Pass |
| Remove T3 from packaged `segment_tiers.json` | Named catalog test fails | Pass |
| Force `DROPPED` instead of `UNKNOWN_ABSENCE` in `silence.py` | Named silence test fails | Pass |

Each mutation was restored before the next check. The focused comparison, lineage,
synthetic-corpus and exporter suite collected and passed 60 tests. A built wheel
installed outside the checkout loaded all three tiers and classified unsupported
absence using T2 from its packaged class catalog.
