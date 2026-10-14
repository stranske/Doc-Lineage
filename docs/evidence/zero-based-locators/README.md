# Zero-based evidence locator proof for issue #86

The production emitter converts one-based physical segment pages to zero-based evidence locator pages exactly once and rejects booleans, non-integers and pages below one. Segment APIs, IDs, schema and viewer anchors are unchanged. Caller locator mappings are not mutated.

Commands from the repository root:

- `python3 -m pytest tests/emit/test_evidence_object.py tests/ingest/test_ingest_synthetic_pdf.py -q`: original production code with the new regressions produced **13 failed, 25 passed**.
- `python3 -m pytest tests/ingest/test_ingest_synthetic_pdf.py tests/emit/test_evidence_object.py tests/blackline/test_section_id_pairing.py -q`: final code **46 passed**. The physical PDF test independently reads the committed two-page PDF with pypdf, checks each emitted excerpt belongs to the page its zero-based locator identifies, and binds evidence files to one-based segments. Manifest evidence sizes and SHA256 values are checked.
- `python3 -m pytest -q --cov=src --cov-report=term-missing`: final full suite **360 passed**, **91.14% coverage**, satisfying the unchanged 80% floor. Two environment dependency warnings remain in the transcript.

Independent controls run with `python3 -m pytest tests/emit/test_evidence_object.py tests/ingest/test_ingest_synthetic_pdf.py -q -k '<selection>'`:

1. Replace `resolved_locator["page"] = span.page - 1` with `span.page`; select `locator_carries or locator_page_and_order or evidence_locators_identify`: **5 failed**, then **5 passed** after exact restoration.
2. Remove the `span.page` validation guard; select `locator_rejects_invalid_source_page`: **7 failed**, then **7 passed** after exact restoration. Some invalid inputs still fail schema validation, but only the production guard guarantees the required ValueError before payload publication.

`mutations.json` binds mutant and restored source hashes. `source-binding.json` binds the base, original emitter, final emitter, tests and PDF. Raw log/JUnit outcomes are retained; local usernames, hostnames, interpreter/worktree/run/temp locations are replaced with placeholders. Only metadata was sanitized; XML parses and JUnit outcome counts were verified unchanged. Original private logs remain in the automation receipt.

Ruff, Black and diff checks pass. Focused mypy passes with `--no-warn-unused-ignores` because unchanged optional Docling import ignores become unused with this local environment; unadjusted mypy reports only those two imported-file warnings. No typing policy was changed. Native PDF-viewer rendering and hosted/provider/post-merge acceptance remain unverified.
