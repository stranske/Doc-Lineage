# Content identity at the lineage publication boundary

`build_supersession_chain` requires every `DocumentRef.content_hash` and both
endpoints of every supplied supersession claim to be exactly 64 lowercase ASCII
hexadecimal characters, representing SHA-256. Malformed identifiers raise
`ValueError` before any edges are returned, including unclaimed records and
calls without evidence. Empty, padded, uppercase, truncated, and nonhex values
are rejected rather than normalized or replaced with filename-derived IDs.

The manifest publisher uses the same claim validator and computes content
digests from the scanned files. Invalid claims abort before an existing manifest
is replaced. Unknown well-formed digests, self-links, competing predecessors,
cycles, and malformed evidence remain errors.

Digest syntax does **not** prove original-byte provenance. A caller constructing
`DocumentRef` must hash the original document bytes, for example with
`doc_lineage.identity.sha256_bytes(original_bytes)`. A well-formed invented digest
can pass syntax validation; the library cannot authenticate bytes it never sees.
The caller also supplies and owns the truth of the specific version notice,
content comparison, or dated owner assertion used as supersession evidence.

Valid content pairs retain their explicit evidence and deterministic ordering.
Duplicate bytes share an identity. Filename prefixes remain unconfirmed hints
and never establish a confirmed edge by themselves.

Run the public-boundary regressions with:

```bash
python3 -m pytest tests/lineage/test_supersession_evidence.py \
  tests/lineage/test_supersession_chain.py tests/test_identity_manifest.py -q
```

The named `test_malformed_content_hashes_rejected` exercises both endpoints with
and without claims. Additional checks reject unclaimed invalid records and
malformed claim endpoints through both publishers, preserving an existing
manifest on rejection. The PR evidence records original failure and production
validation-bypass failure followed by byte-identical restoration and success.
