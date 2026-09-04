# Doc-Lineage

Document lineage and blackline engine for recurring investment documents.

**Status:** created 2026-09-04 as part of the Research Program 2026-09 (see `stranske/Ready` → `research-program/`). Scope, architecture and first issues arrive from research briefs R1 (legal-document decomposition) and R2 (consultant-report diffing). Until then this repo carries only the Workflows consumer scaffold.

## Intent

- Take two or more versions of a recurring document (PPM, LPA, side letter, consultant report, manager letter, DDQ) and produce:
  - a **blackline** (what changed, where, classified by kind of change),
  - a **lineage** (which document supersedes which; families of documents descending from a common template),
  - a set of **tracked variables** — clauses, defined terms, and recurring work units — extracted into a stable schema so documents and counterparties can be compared.
- Run without servers: a Python library plus a static/offline review surface, producing HTML and CSV artifacts with one-click links back to the source document and page.
- **Synthetic and public data only** in this repository. No proprietary manager material is ever committed or used in tests.

## Interoperability

Identifiers and evidence objects follow the fleet conventions in `docs/contracts/` (`run-contract/v1`, `evidence-object/v1`, identity-map conventions). Document-type and clause vocabularies will be published as data files so sibling repos (`Inv-Man-Intake`, `Manager-Database`, `Pension-Data`) can adopt the same names.

## Scope, fixed 2026-09-04 by the work-environment inventory

The owner's work environment answered a structured information request, and its answers pin this repo's scope. The relevant facts:

- The document library is already a synced folder tree, one folder per manager then one per document category, holding roughly 3,800 PDFs, 480 spreadsheets and 170 Word documents in the manager portion alone. There is no document-management system to integrate with.
- **There are no stable document identifiers.** The filename is the de facto identifier and supersession is an ad hoc numeric-prefix convention. One existing tool already derives a content-hash identifier because path-based keys silently orphaned data whenever a document was renamed. Identity therefore has to be computed, and it has to survive renames.
- **A real minority of legal documents are scanned images with no text layer.** One recognition pass recovered more than twenty documents and five hundred pages that every prior text-based analysis had silently skipped. Optical character recognition is a required stage, not an enhancement, and any coverage figure computed without it is wrong.
- Three separate extraction implementations exist there today, each solving page pointers, content hashing and recognition fallback slightly differently. This repo replaces all three with one library.
- Two comparison tools already run there with real, named schemas: a consultant-report tracker with change, continuity, persistence and stale-flag ledgers, a section crosswalk, a five-value segment vocabulary and three materiality tiers; and a legal-document lineage tool with a seven-column material-change ledger and a three-tier materiality taxonomy mapped to named source fields. **This repo adopts those field names rather than inventing new ones.**

So the build order is: document identity and manifest, extraction with page pointers and a recognition fallback, the tracked-variable schema taken from the two existing tools, then the lineage and comparison engine. Rendering belongs to `stranske/Deliverable-Render`, not here.
