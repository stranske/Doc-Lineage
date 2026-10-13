# Docling item boundary proof

Issue #88. The production adapter now separates Docling text items with blank lines, which the existing ingest paragraph splitter already preserves. Single newlines inside items still normalize as paragraph whitespace. Page pointers and `<sha16>-pNNNN-sNNNN` segment-ID format are unchanged. No offline extraction or blackline algorithm changed.

The converter alone is stubbed: tests run the real adapter, immutable snapshot handling, segmenter, persisted ingest artifacts and section-ID blackline pairing. Three items (title and two numbered clauses with bodies) produce three segments and two sections. Separate headers/bodies remain separate; clause2's continuation on page2 belongs to section2, a clause2 edit leaves section1 unchanged, repeated input yields identical IDs, and written artifact hashes/byte lengths match the manifest.

- `python3 -m pytest tests/ingest/test_docling_segmenter.py tests/blackline/test_section_id_pairing.py tests/ingest/test_ingest_synthetic_pdf.py -q --junitxml=docs/evidence/docling-item-boundaries/focused.xml`: **53 passed, zero skipped** (`focused.log/xml`).
- `python3 -m pytest --cov=src/doc_lineage --cov-report=term-missing --cov-fail-under=80 --junitxml=docs/evidence/docling-item-boundaries/full.xml`: **354 passed, zero skipped, 91.13% coverage**,80% required (`full.log/xml`).
- Original main adapter with current regressions: **4 assertion failures**, zero errors (`original-red.log/xml`).
- Independently replace only the blank-line item join with one newline: **4 assertion failures**, zero errors (`mutation-red.log/xml`). Restore exact source bytes: **4 passed** (`restored-green.log/xml`). SHA256 bindings/restoration in `mutation.json`.
- Offline synthetic PDF smoke (`offline-smoke.json`) retains exact section IDs1/2/3/4 and one-based segment page provenance; no offline fixtures modified.

Ruff, Black and whitespace checks pass. Unadjusted local mypy reports two unused-ignore errors on unchanged optional Docling import suppressions; the two-source check passes with only `--disable-error-code unused-ignore`, with typing policy unchanged. Real installed-Docling model output, native viewer verification, hosted complete-check topology and postmerge provider acceptance are UNKNOWN.

`source-binding.json` binds source/tests/input bytes. `SHA256SUMS` binds published proof bytes. Logs/JUnit redact private host/user/temp paths without changing test outcomes; original raw outputs are retained in the automation receipt outside Git.
