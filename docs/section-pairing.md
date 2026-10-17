# Persisted PDF section pairing

This local command pairs numbered sections from **extracted PDF text**. It does
not classify text differences, establish semantic supersession, convert PDF to
DOCX, or produce native DOCX tracked changes. Duplicate IDs, unmatched sections
and low-confidence headers still require manual review through the existing
`build_section_tree` / `align_sections` engine.

```bash
python -m doc_lineage.cli ingest before.pdf --output before --no-docling --no-ocr
python -m doc_lineage.cli ingest after.pdf --output after --no-docling --no-ocr
python -m doc_lineage.cli pair-sections before after --store comparisons
# stdout: cmp_<32 lowercase hex>
python -m doc_lineage.cli lookup-section-pairing cmp_<32 lowercase hex> --store comparisons
# Optional assertions of intended order and options:
python -m doc_lineage.cli lookup-section-pairing cmp_<32 lowercase hex> \
  --store comparisons --original-run before --modified-run after --threshold 0.8
```

`--no-docling --no-ocr` selects the standard offline text path. Pairing and
lookup load persisted bytes only; they never invoke OCR, converters, Office,
native helpers, model downloads, or a service. Partial text coverage remains
recorded in the bound segments artifact; pairing does not certify complete PDF
coverage. Pages and section recognition retain the ingest backend's limits.

The Python API is `create_section_comparison(original_run, modified_run,
store=Path(...), threshold=0.8)` and `load_section_comparison(id,
store=Path(...), original_run=None, modified_run=None, threshold=None)` in
`doc_lineage.blackline`. Creation returns the opaque ID. Lookup returns the
validated record and has no write operation. Supplying one asserted run requires
supplying both. Threshold must be finite and within [0, 1]. Omitted lookup
threshold reuses the recorded threshold.

## Local identity and artifact

`section-pairing-comparison/v1` is a **repo-owned** envelope, independent of the
shared fleet run/manifest schemas. It contains:

- `comparison_id`: random `cmp_<32 lowercase hex>`, sharing the opaque ID syntax
  inspected read-only in DOCX PR #127 at
  `89542e1103330e076ce1afad24091e3428fd56ee` (source #110).
- `identity`: `comparison-identity/v1`, mode `extracted-pdf-sections`, ordered
  `original` and `modified` bindings, and `options` containing
  `header_confidence_threshold` and engine `section-id/v1`.
- Each binding includes full lowercase SHA-256 digests of the original bytes,
  `segments.json` bytes and `artifact-manifest.json` bytes.
- `identity_sha256`: SHA-256 of canonical identity JSON; `decisions`: existing
  `lineage-edges/v1` pairing records; `runs`: store-relative input locators.
- `record_sha256`: SHA-256 of the canonical record excluding this field.
  Canonical JSON uses sorted keys, compact separators, no NaN, UTF-8 and a
  trailing newline (Python `json.dumps` default ASCII escaping).

PR #127's separate schema is `docx-comparison/v1`, with ordered
`original_sha256` / `modified_sha256` package digests. The common conventions are
an opaque ID, a versioned record, original-byte identity and explicit order.
The section schema nests these digests beside extraction bindings and carries an
explicit mode. Neither loader accepts the other schema. This implementation is
based on main; it does not import or stack #127's unmerged implementation.
Native DOCX-by-ID acceptance and README issue #15 completion remain pending that
separate scope. No shared workflow, identity convention or fleet schema changes.

An ingest now retains a content-addressed `source-<sha256>.bin` snapshot and lists
it in the existing manifest. It uses the same bytes that were parsed. External
source files remain untouched; comparison needs only the two ingest directories.
A repeated ingest can reuse an identical retained snapshot, but cannot overwrite
a different snapshot at the same content-addressed name. Reusing a run directory
for different input retains older original snapshots and updates its current
manifest/segments: an existing comparison then fails its original bindings.
Use separate directories for versions and retain them for replay. Legacy runs
without a manifested original snapshot fail with a re-ingest instruction; the
loader does not guess a source from a filename or claim to verify absent bytes.

Every manifested file must exist, match its hash and byte count, and have a
unique safe relative path and artifact ID. Symlinked files/path components and
traversal are rejected. Segment schema/source binding, order, IDs, page order,
counts and text structure are checked before pairing. Original bytes must be
PDF bytes and match both original-artifact and manifest-source bindings.

## Replay and failure behavior

Creation validates everything before creating the store. A private temporary
file is linked atomically and exclusively into `<store>/<id>.json`; collisions
never overwrite records. Records have no update API. Repeating a comparison
creates a new opaque ID; identical ordered inputs/options have the same identity
digest. Reversing order or changing options produces a different identity.
Relative locators allow moving a **complete bundle** of store and runs while
preserving their relative layout; keep both manifests and originals intact.

Lookup accepts an ID only, never a path. It checks record checksum, schema, mode,
ID, all live input bindings, optional order/options assertions, then replays the
same engine and compares decisions before returning JSON. Unknown IDs, missing
or deleted sources/artifacts, malformed manifests/segments, input/record tamper,
source-order mismatch and options mismatch raise `ValueError` (CLI exit 1 with
stderr and no stdout). Validation does not republish or repair artifacts. Store
I/O errors also return exit 1. Wrong command syntax is argparse exit 2.

Checksums detect corruption and accidental modification, not a malicious actor
rewriting every local record and checksum. These are trusted local records, not
signed attestations. A future engine change needs explicit version/migration
policy; a replay decision mismatch fails rather than silently rewriting history.
