# Deliberate-break evidence: per-page OCR fallback gate (#37 / #3)

Linked issue: `stranske/Doc-Lineage#37` (parent gate `#3`).

## Mutation (temporary, reverted before merge)

In `src/doc_lineage/extract/pdf.py`, text-layer detection was temporarily scoped to the whole document: when any page has extractable text, pages without a text layer skip OCR and are counted as `text_layer` with empty spans.

```python
    document_has_text_layer = any(
        (page.extract_text() or "").strip() for page in reader.pages
    )
    ...
    if document_has_text_layer:
        return [], "text_layer"
```

Production code on this branch keeps per-page detection; this file records the RED/GREEN transcript only.

## RED — `pytest tests/test_extract_coverage.py::test_mixed_pdf_recognizes_only_missing_text_layer_page -q`

```
>       assert document.coverage.pages_with_text_layer == 1
E       AssertionError: assert 2 == 1
E        +  where 2 = CoverageStats(pages_with_text_layer=2, pages_recognized=0, pages_unreadable=0).pages_with_text_layer
FAILED tests/test_extract_coverage.py::test_mixed_pdf_recognizes_only_missing_text_layer_page
============================== 1 failed in 7.85s ===============================
```

## GREEN — same command after revert

```
tests/test_extract_coverage.py .                                         [100%]
============================== 1 passed in 7.78s ===============================
```

## Verification command (this PR)

`pytest tests/test_extract_coverage.py::test_mixed_pdf_recognizes_only_missing_text_layer_page -q`
