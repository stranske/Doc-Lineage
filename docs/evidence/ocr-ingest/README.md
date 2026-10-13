# OCR ingest integration proof — issue #92

Base: `e816478bf30402766976b5cd0de40e578868e7f9`, PR #87. This PR is
explicitly stacked to reuse its zero-based evidence emitter. Do not merge the
OCR PR until #87 merges and source #86 is dispositioned; then rebase/retarget
onto main (including the already-merged #89 paragraph boundary change), rerun
validation, and establish a fresh exact-head review floor.

## Observable behavior

Synthetic image-only PDFs are rendered by real PDFium, then recognized by a
deterministic local recognizer. Actual ingest, paragraph segmentation,
manifest publication, schema validation, evidence excerpts/methods/zero-based
locators and artifact byte hashes are asserted. The recognizer receives a
nonblank rendered image. A mixed native-plus-two-scanned-page document invokes
recognition only for the two missing pages; one recovered and one unreadable
page produce `coverage.status=partial`, with 1 native, 1 recognized and 1
unreadable page. Segment methods and evidence methods remain page-specific.
Changing the source path after the bounded read does not change OCR input,
source SHA256 or manifest source byte count. Repeated input/recovery produces
the same segment and evidence IDs.

Absent backends, disabled OCR, unavailable rendering, empty recognition and
recognizer exceptions never fabricate text; an entirely unrecoverable document
fails before creating output. The CLI emits coverage and outstanding page
warnings, and `--no-ocr` preserves the nonzero all-scanned failure.

## Commands and results

`python3 -m pytest tests/ingest/test_ingest_synthetic_pdf.py tests/test_extract_coverage.py tests/emit/test_evidence_object.py -q`

- Focused: **62 passed**, no skipped tests (`focused.log` / `focused.xml`).
- Full: `python3 -m pytest --cov=src --cov-report=term-missing`: **372 passed**,
  no skipped tests, **91.23%** coverage against an unchanged 80% floor
  (`full.log` / `full.xml`).
- Ruff, Black and whitespace checks pass. Local unadjusted mypy reports two
  pre-existing unused-ignore diagnostics in the imported optional Docling
  adapter (lines 110/111); checking the three changed sources with
  `--no-warn-unused-ignores` passes. No typing or test policy changed.

## Falsification and restoration

`original-behavior.json` records the exact unmodified base ingest module
failing to recover a real synthetic scanned page with its original API and
publishing nothing. The nine new integration regressions initially failed
because the OCR API/default hook did not exist (`original.log`); this is API
absence evidence, not nine independent behavioral assertions.

After implementation, temporarily bypassing ingest recovery made
`tests/ingest/test_ingest_synthetic_pdf.py::test_ingest_recovers_image_only_page`
fail with no recovered segments; restoring the exact source bytes returned
**1 passed**. Temporarily replacing the per-segment evidence method with the
document-wide method made
`tests/ingest/test_ingest_synthetic_pdf.py::test_mixed_ingest_keeps_page_methods_and_partial_coverage`
fail on the OCR evidence method; exact restoration returned **1 passed**.
`mutations.json` binds both restoration checks to the final ingest source
SHA256. The full suite ran after both sources were restored and stable.

`source-bindings.json` binds the final production and regression files;
`SHA256SUMS` binds this proof packet. Published logs redact local account,
interpreter and temporary paths only; JUnit files remain valid XML and retain
the same outcomes. Raw logs stay in the automation run receipt.

Real Tesseract accuracy, real Docling/model behavior, physical/native viewer
acceptance and hosted/post-merge provider verdicts remain **UNKNOWN**. No
hosted service, OCR dependency requirement or extraction cache wire change
was introduced.
