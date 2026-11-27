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

## Section heading grammar (`section-id/v2`)

The offline text producer flattens a page into one segment, so several numbered
headings can sit inside a single segment. `build_section_tree` therefore splits
segments on a **bounded** inline grammar rather than only on segment-start
headers:

- A heading is `<int>. <TITLE>`, where `<TITLE>` is one or more words of two or
  more uppercase ASCII letters separated by spaces/tabs, not followed directly by
  another letter or digit (`2. TERMs` is not a heading).
- It must start at the beginning of a line, or immediately after sentence-ending
  punctuation (`.`, `!`, `?`) plus whitespace — e.g. `...L.P. 1. MANAGEMENT FEE`.
- Rejected: lowercase or mixed-case titles (`1. Management fee`), single-letter
  words (`3. A notice`), decimals (`1.75%`), and mid-clause enumerations not
  preceded by a sentence end (`include 1. FEES and 2. TERM`).

Each split section keeps the source `segment_id`; a segment that holds the end
of one section and the start of another is listed in both sections'
`segment_ids`. Header confidence is `1.0`. This is not universal PDF section
recognition: non-uppercase headings, unnumbered headings, `Section 1.` /
`1.1` styles, and headings mangled by the extraction backend stay unrecognized.
Semantic fallback is out of scope.

**Unassigned text.** `unassigned_char_count` is the number of characters, after
trimming surrounding whitespace, of segment text that appears before the first
recognized heading in the document (for example a title block or recitals).
`unassigned_segment_ids` lists, in order, each segment contributing such text.
Text after a heading always belongs to that section, so these values are zero
exactly when the document begins with a recognized heading. They are recorded
on `DocumentSections` and in the comparison record, recomputed on lookup, and
`pair-sections` prints a stderr warning for each side whose count is above
zero (exit code and stdout are unchanged).

## Local identity and artifact

`section-pairing-comparison/v1` is a **repo-owned** envelope, independent of the
shared fleet run/manifest schemas. It contains:

- `comparison_id`: random `cmp_<32 lowercase hex>`, sharing the opaque ID syntax
  inspected read-only in DOCX PR #127 at
  `89542e1103330e076ce1afad24091e3428fd56ee` (source #110).
- `identity`: `comparison-identity/v1`, mode `extracted-pdf-sections`, ordered
  `original` and `modified` bindings, and `options` containing
  `header_confidence_threshold` and engine `section-id/v2`.
- Each binding includes full lowercase SHA-256 digests of the original bytes,
  `segments.json` bytes and `artifact-manifest.json` bytes.
- `identity_sha256`: SHA-256 of canonical identity JSON; `decisions`: existing
  `lineage-edges/v1` pairing records; `runs`: store-relative input locators;
  `unassigned`: per-side (`original`, `modified`) `unassigned_char_count` and
  `unassigned_segment_ids` (see *Section heading grammar* above).
- `record_sha256`: SHA-256 of the canonical record excluding this field.
  Canonical JSON uses sorted keys, compact separators, no NaN, UTF-8 and a
  trailing newline (Python `json.dumps` default ASCII escaping).

PR #127's separate schema is `docx-comparison/v1`, with ordered
`original_sha256` / `modified_sha256` package digests. The common conventions are
an opaque ID, a versioned record, original-byte identity and explicit order.
The section schema nests these digests beside extraction bindings and carries an
explicit mode. Neither loader accepts the other schema. Both implementations coexist after merging main at
`c274b866e695d92a083c182c19f3119cab01e0b0` (including merged PR #127).
Section pairing produces no DOCX output. DOCX export by comparison ID is a
separate, shipped mode; see [Comparison records](../README.md#comparison-records).
No shared workflow, identity convention or fleet schema changes.

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

Ingest run/evidence directories are owner-only (`0700`); snapshots, segments,
manifest and evidence files are `0600`, including reused runs and retained
originals. Snapshots are written and synced in a private temporary file, then
published exclusively. Interrupted writes cannot expose a partial final snapshot.

Every manifested file must exist, match its hash and byte count, and have a
unique safe relative path and artifact ID. Symlinked files/path components and
traversal are rejected. Segment schema/source binding, order, IDs, page order,
counts and text structure are checked before pairing. Original bytes must be
PDF bytes and match both original-artifact and manifest-source bindings.

## Replay and failure behavior

Creation validates everything before creating the store. A private temporary
file is linked atomically and exclusively into `<store>/<id>.json`; collisions
never overwrite records. The temporary file is synced before linking; temporary
cleanup is followed by a directory sync before returning an ID. A directory-sync
failure reports an I/O error even if a complete final file already exists; its
durability is then unknown. Records have no update API. Repeating a comparison
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

**`section-id/v1` records are rejected.** v1 recognized only segment-start
headers, so its decisions cannot be reproduced by v2 replay. Lookup of a record
whose engine is `section-id/v1` raises `ValueError` naming the retired engine
(CLI exit 1) before any replay; any other unknown engine is rejected the same
way. There is no in-place migration: run `pair-sections` again on the retained
ingest runs to create a new v2 comparison ID.

### Local filesystem capability boundary

On the tested POSIX runtime, private artifacts use descriptor chmod0600 and
publication syncs file bytes followed by the containing directory. Real sync
errors propagate. Where `O_DIRECTORY` is absent, publication emits a RuntimeWarning
and directory durability is unsupported. Where `fchmod` is absent, path chmod
runs before payload writes and emits a RuntimeWarning: owner-only privacy is
unverified on that platform. Chmod errors propagate. This compatibility path
does not establish Windows ACL, Office, or hardware power-loss guarantees; it
requires no installer, helper, security approval, or privacy-setting changes.
