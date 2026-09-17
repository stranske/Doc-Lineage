# Public fixture corpus

Fleet-wide fixture manifest for Doc-Lineage extraction and lineage tests (B2-037).

## Layout

- `manifest.json` — `artifact-manifest/v1` catalog of synthetic library PDFs plus one
  CalPERS Investment Committee public entry with provenance fields (`source_url`,
  `content_sha256`, `doc_type_id`).
- `calpers/ic/default.pdf` — committed synthetic stand-in PDF whose digest matches the
  manifest. The `source_url` records the canonical CalPERS IC meeting page for provenance;
  replace this file with a downloaded IC attachment when exercising live public-PDF
  extraction, then update `sha256` / `content_sha256` / `bytes` together.

## Git LFS

If the CalPERS fixture is replaced with a large public PDF, track it with Git LFS:

```bash
git lfs install
git lfs track "tests/fixtures/public_corpus/calpers/**/*.pdf"
```

Verify the on-disk digest matches the manifest after any replacement:

```bash
mkdir -p tests/fixtures/public_corpus/calpers/ic
shasum -a 256 tests/fixtures/public_corpus/calpers/ic/default.pdf
python3 scripts/validate_fixture_manifest.py
```

## Validation

```bash
python3 scripts/validate_fixture_manifest.py
pytest tests/fixtures/test_public_corpus_manifest.py -q
```
