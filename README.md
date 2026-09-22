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
writes DOCX bytes to standard output. Input files remain unchanged.

Here `--blackline` is a boolean flag for a file-pair comparison. The planned
`--blackline <id>` interface in [issue #15](https://github.com/stranske/Doc-Lineage/issues/15)
is not implemented: it needs a persisted comparison-ID lookup contract connecting
[ingest #8](https://github.com/stranske/Doc-Lineage/issues/8) and
[blackline #10](https://github.com/stranske/Doc-Lineage/issues/10). Ingest excludes
blackline/diff, and the section-pairing issue does not yet define that lookup.
A path is not treated as a substitute comparison ID. File-pair export therefore
does not complete the ID-based scope of #15.

Source distributions include the export tests under `tests/export/` and their
`tests/fixtures/fact_key_map/tracked_variables.json` fixture so the native
tracked-changes acceptance tests can be run from the source archive.

## Intent

- Take two or more versions of a recurring document (PPM, LPA, side letter, consultant report, manager letter, DDQ) and produce:
  - a **blackline** (what changed, where, classified by kind of change),
  - a **lineage** (which document supersedes which; families of documents descending from a common template),
  - a set of **tracked variables** — clauses, defined terms, and recurring work units — extracted into a stable schema so documents and counterparties can be compared.
- Run without servers: a Python library plus a static/offline review surface, producing HTML and CSV artifacts with one-click links back to the source document and page.
- **Synthetic and public data only** in this repository. No proprietary manager material is ever committed or used in tests.

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
visible in `document.coverage.pages_unreadable`.

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
