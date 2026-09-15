# Public fixture corpus

Fleet-wide fixture manifest for Doc-Lineage extraction and lineage tests (B2-037).

## Layout

- `manifest.json` — `artifact-manifest/v1` catalog of synthetic library PDFs plus one
  CalPERS Investment Committee public entry with provenance fields (`source_url`,
  `content_sha256`, `doc_type_id`).
- `calpers/ic/default.pdf` — **not committed**; fetch via Git LFS or the download helper
  below when running extraction tests against the public CalPERS entry.

## Git LFS

Large public PDFs must not be committed inline. After installing Git LFS:

```bash
git lfs install
git lfs track "tests/fixtures/public_corpus/calpers/**/*.pdf"
```

Populate the CalPERS IC PDF locally (hash must match `content_sha256` in the manifest):

```bash
python3 scripts/validate_fixture_manifest.py --manifest tests/fixtures/public_corpus/manifest.json
curl -fsSL -o tests/fixtures/public_corpus/calpers/ic/default.pdf \
  'https://www.calpers.ca.gov/sites/default/files/spf/img/lincoln-plaza-building-guide-street-map.pdf'
shasum -a 256 tests/fixtures/public_corpus/calpers/ic/default.pdf
```

The default entry uses the CalPERS IC meeting page as the canonical `source_url`; replace
the downloaded file with an IC agenda attachment from that page when exercising consultant
report diffing. Update `content_sha256` / `sha256` together if the golden PDF changes.

## Validation

```bash
python3 scripts/validate_fixture_manifest.py
pytest tests/fixtures/test_public_corpus_manifest.py -q
```
