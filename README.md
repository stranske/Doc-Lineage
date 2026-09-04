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
