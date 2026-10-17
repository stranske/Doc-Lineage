# Doc-Lineage

Document lineage and blackline engine for recurring investment documents.

**Status:** created 2026-09-04 as part of the Research Program 2026-09 (see `stranske/Ready` → `research-program/`). Scope, architecture and first issues arrive from research briefs R1 (legal-document decomposition) and R2 (consultant-report diffing). The initial legal clause vocabulary and Python loader are available; the document processing engine remains to be implemented.

## DOCX tracked-changes export

Install the package and compare two DOCX files with the bundled local engine:

```bash
doc-lineage export-docx --original original.docx --modified revised.docx \
  --blackline --output redline.docx --author Counsel
```

The command writes native Word insertion/deletion markup. Without `--output`, it
writes DOCX bytes to standard output. Input files remain unchanged: destinations
that alias either input, including symbolic and hard links, are rejected.

## Comparison records

Create a local record, then export by ID in another process (even from another
working directory):

```bash
doc-lineage create-comparison --original original.docx --modified revised.docx
# prints cmp_<32 lowercase hexadecimal characters>
doc-lineage export-docx --blackline cmp_<printed value> --output redline.docx
```

Each JSON record has `schema_version: "docx-comparison/v1"`, a random UUID4-based
`comparison_id` (`cmp_` followed by 32 lowercase hex characters), ordered
`original_path` / `modified_path` absolute DOCX locations, and
`original_sha256` / `modified_sha256` digests of the complete original packages.
Records are created exclusively as `<ID>.json` in `~/.doc-lineage/comparisons`.
Use `--comparison-store /absolute/local/directory` on both commands to select a
different store. The ID is separate from ingest run IDs and content identities;
a filesystem path is never a comparison ID. Unknown IDs, malformed records and
unsupported schema versions fail explicitly.

At every ID export, both files are reopened and their bytes checked against the
stored SHA-256 digests before those same buffers reach the native redline renderer.
Missing/deleted sources or changed bytes fail without publishing output, including
stdout. An ID cannot be combined with replacement input paths. The bare boolean
`--blackline` file-pair form above remains available. Output aliases of either
source or the selected comparison record are rejected.

Retain the original DOCX files and any ingest manifests locally as immutable
evidence; these commands neither edit them nor copy them into a managed archive.
Records preserve source locations and hashes, not backup bytes: moving or deleting
an input prevents replay, and the CLI never silently substitutes another source.
This is a DOCX/package comparison through the existing tracked-changes renderer,
with its existing fidelity limits. Extracted-PDF text/section comparison remains a
distinct mode: it does not preserve DOCX layout, generate a Word package, or imply
PDF-to-DOCX conversion. No hosted service or database is required.

Source distributions include the export tests under `tests/export/` and their
`tests/fixtures/fact_key_map/tracked_variables.json` fixture so the native
tracked-changes acceptance tests can be run from the source archive.

## Intent

- Take two or more versions of a recurring document (PPM, LPA, side letter, consultant report, manager letter, DDQ) and produce:
  - a **blackline** (what changed, where, classified by kind of change),
  - a **lineage** (which document supersedes which; families of documents descending from a common template),
  - a set of **tracked variables** — clauses, defined terms, and recurring work units — extracted into a stable schema so documents and counterparties can be compared. The initial evidence-bearing `extract-variables` CLI supports only the documented management-fee forms; inspect its `unresolved.json` for unasserted clauses. See [extraction coverage](docs/contracts/tracked-variable-v1.md#extraction-coverage) for the offline ingest → extraction → fact-map commands.
- Run without servers: a Python library plus a static/offline review surface, producing HTML and CSV artifacts with one-click links back to the source document and page.
- **Synthetic and public data only** in this repository. No proprietary manager material is ever committed or used in tests.

## Confirmed document supersession

Filename prefixes suggest order; they do not establish supersession. Manifest
rows expose the suggested predecessor as `supersession_hint`, while `supersedes`
and `supersession_evidence` remain null until explicit evidence is supplied.
`build_supersession_chain` likewise returns no confirmed edges by default.

Both Python APIs accept `supersession_evidence`, keyed by the pair
`(prior_sha256, successor_sha256)` of original content digests:

```python
from pathlib import Path
from doc_lineage.manifest import write_manifest

claims = {
    (prior_sha256, successor_sha256): {
        "mechanism": "owner_assertion",
        "detail": "Corpus owner, 2026-10-13: the revised terms replace the prior terms.",
    }
}
write_manifest(Path("library"), Path("manifest.jsonl"), supersession_evidence=claims)
```

Pass the same mapping to `build_manifest_rows` or `build_supersession_chain`.
The allowed mechanisms are `source_metadata`, `content_comparison`, and
`owner_assertion`; each needs a specific nonempty string `detail`. The caller
supplies the actual notice, comparison, or dated assertion; the library validates
its structure and content binding, and does not invent or independently verify
that assertion. Evidence can connect renamed documents independently of filename
order. Both endpoints must exist in the supplied corpus. Self-links, multiple
predecessors, and cycles raise `ValueError` before publication.

All supplied lineage content IDs and claim endpoints must be lowercase SHA-256
digests, including records without claims. Invalid IDs raise before publication;
syntax validation cannot authenticate the caller's original-byte provenance.
See [the content identity boundary](docs/lineage-content-identity.md) for the
contract, migration from placeholder IDs, and public-API verification commands.

Claims apply to content identities, so identical copies share confirmed lineage.
Filename hints remain path-scoped. Renames preserve claims, but changed bytes
require a new claim. Supply evidence on every manifest scan: old serialized
claims are not silently trusted, and a scan without evidence clears old confirmed
links, including legacy filename-only links. The existing CLI scan supplies no
claims and therefore emits hints only. Text-layer annotations and unchanged-row
byte preservation retain their existing behavior.

## Ingest (M1)

`doc-lineage ingest` parses one document, splits it into page-anchored segments, and
writes a run directory containing `segments.json` and an `artifact-manifest.json`
conforming to `artifact-manifest/v1` (`docs/contracts/schemas/`):

```bash
doc-lineage ingest tests/fixtures/synthetic_lpa.pdf --output /tmp/out
```

Docling is the intended segmenter. It is an optional dependency, so the adapter falls
back to reading the PDF's own content streams when Docling is not importable, and every
run records which backend produced the text (`backend` in `segments.json`) so fallback
output is never mistaken for a Docling parse. Pages with no readable text layer are
reported in `pages_without_text_layer` rather than dropped — recognition (issue #3) is a
required stage here, so a page that yields nothing is a finding, not a silence.

Ingest now attempts local OCR for PDF pages the segmenter could not read, using
its existing bounded source-byte snapshot. Install the optional `ocr` extra and
local Tesseract to enable recognition; neither is mandatory. Python callers can
supply `ingest_document(..., ocr_backend=backend)` and disable recognition with
`ocr_enabled=False`; the CLI provides `--no-ocr`.

`segments.json` records each segment's `method` (`text`, `parser`, or `ocr`),
`unreadable_pages`, and `coverage` with `status` (`complete` or `partial`), total,
native, recognized, and unreadable page counts. `pages_without_text_layer`
retains the original segmenter's page findings even after recovery; only
`unreadable_pages` represents outstanding recovery. Page lists and segments are
one-based; emitted evidence locators follow the contract's zero-based pages.
The CLI prints coverage and warns about outstanding unreadable pages. Partial
ingest can still return 0 with that warning; an entirely unrecoverable document
returns 1 and publishes nothing. Recognition failure or a missing renderer never
creates placeholder text. Deterministic recognizer tests validate integration,
not Tesseract transcription accuracy.

## PDF extraction for metric consumers

The public extraction API returns page-attributed spans with two text views:

```python
from doc_lineage.extract import ExtractCache, extract

document = extract("report.pdf", cache=ExtractCache())
for span in document.spans:
    print(span.page, span.text)  # existing normalized text
    print(span.text_lines)      # source lines before PDF whitespace normalization
```

`text_lines` preserves line breaks and horizontal spacing within each extracted
line, so neighboring monetary units or percentage markers need not share a
downstream metric-input block. It also preserves the OCR recognizer's lines.
This is extracted text, not a table schema or a guarantee of metric accuracy;
consumers still need value, unit, and provenance tests. Office spans may leave
the additive field as `None`.

Disk caches retain the field. Older native-PDF cache entries without line data
are refreshed from the source; old OCR entries can recover lines from their
unflattened text. `ExtractCache()` uses memory only. OCR still requires the
`ocr` extra and a working local Tesseract installation; unreadable pages remain
visible in `document.coverage.pages_unreadable` and as one-based page numbers in
`document.coverage.unreadable_pages` (recomputed on every extraction, including
cache hits, without storing coverage in the cache).

Run `python -m pytest tests/test_extract_lines.py tests/test_extract_coverage.py -q`
to verify preserved lines, page attribution, OCR routing, and cache reloads.

## Interoperability

Identifiers and evidence objects follow the fleet conventions in `docs/contracts/` (`run-contract/v1`, `evidence-object/v1`, identity-map conventions). The versioned [legal clause vocabulary](vocab/legal-clauses.json) publishes 25 stable `ontology_key` values so sibling repos (`Inv-Man-Intake`, `Manager-Database`, `Pension-Data`) can adopt the same names. Load the full document with `from doc_lineage.vocab import load_legal_clauses` and `load_legal_clauses()`.

The keys adapt topics from [ILPA Principles 3.0](https://ilpa.org/wp-content/uploads/2019/06/ILPA-Principles-3.0_2019.pdf) and [CUAD v1](https://www.atticusprojectai.org/cuad/) (CC BY 4.0), with withdrawal fields supplied by the B2 owner default. Each entry records its source. `non_authoritative: false` identifies the canonical project vocabulary; these are project-defined identifiers, not identifiers issued by ILPA or CUAD or recommended contract terms.

## Scope, fixed 2026-09-04 by the work-environment inventory

The owner's work environment answered a structured information request, and its answers pin this repo's scope. The relevant facts:

- The document library is already a synced folder tree, one folder per manager then one per document category, holding roughly 3,800 PDFs, 480 spreadsheets and 170 Word documents in the manager portion alone. There is no document-management system to integrate with.
- **There are no stable document identifiers.** The filename is the de facto identifier and supersession is an ad hoc numeric-prefix convention. One existing tool already derives a content-hash identifier because path-based keys silently orphaned data whenever a document was renamed. Identity therefore has to be computed, and it has to survive renames.
- **A real minority of legal documents are scanned images with no text layer.** One recognition pass recovered more than twenty documents and five hundred pages that every prior text-based analysis had silently skipped. Optical character recognition is a required stage, not an enhancement, and any coverage figure computed without it is wrong.
- Three separate extraction implementations exist there today, each solving page pointers, content hashing and recognition fallback slightly differently. This repo replaces all three with one library.
- Two comparison tools already run there with real, named schemas: a consultant-report tracker with change, continuity, persistence and stale-flag ledgers, a section crosswalk, a five-value segment vocabulary and three materiality tiers; and a legal-document lineage tool with a seven-column material-change ledger and a three-tier materiality taxonomy mapped to named source fields. **This repo adopts those field names rather than inventing new ones.**

So the build order is: document identity and manifest, extraction with page pointers and a recognition fallback, the tracked-variable schema taken from the two existing tools, then the lineage and comparison engine. Rendering belongs to `stranske/Deliverable-Render`, not here.

Comparison catalog authority, mirror refresh commands, and acceptance checks are
documented in [Comparison catalog maintenance](docs/comparison-catalogs.md).

Manifest scans omit documents larger than the ingest limit (currently 100 MiB)
before hashing them, and log each skipped library path and size. The ingest command
rejects the same over-limit document. Split or reduce such a source before adding
it to an ingestable manifest; an omitted document is not an ingest success.

The small [static provenance link helper](docs/triple-link-resolver.md) resolves
document-page, mirror, and source-system links for consumers of tracked variables.
It does not implement the output renderer.
