# Document-identity conformance audit

Source issue: [#94](https://github.com/stranske/Doc-Lineage/issues/94).
Inspected commit: `33cd32ff1e41350d293734b0d16b327cb54c3652` (main after #89 and #91; before #87/#93).
This is a dated source snapshot, not a claim about later heads or native viewers.
No production implementation, fleet convention, schema or dependency changed.

## Result and follow-up ownership

- **Known confirmed-bug, #86/#87:** physical page 1 still emits `locator.page=1` on inspected main. The existing PR #87 fixes this; no duplicate issue or fix is created. Source #86 remains open pending closer acceptance.
- **Known defect now already-correct, #90/#91:** filename ordering produces hints only. Confirmed links require explicit content-bound mechanism/detail evidence. #91 merged as the inspected commit; source #90 is closed after independent comparison disposition. This audit independently exercises the current publishers, without claiming provider PASS.
- **Additional confirmed-bug, [#95](https://github.com/stranske/Doc-Lineage/issues/95):** public lineage publication accepts non-SHA256 content IDs (`hash-old`, `hash-new`) and emits confirmed edges. Exactly one follow-up, with malformed-ID regression criteria, owns this instance. The manifest scanner computes real hashes; it is not the affected producer. A digest-format check alone will not prove authentic byte provenance.
- **needs-investigation:** the generic schema validator accepts contradictory optional `document_ref.page` and `locator.page`. JSON Schema shape validation is its documented boundary, and current local producers do not opt in to `document_ref`; this demonstrates a semantic-validation limitation, not a reproduced misattributed local publication. A future opt-in must enforce equality at its boundary. No mandatory attribution migration is inferred.

The audit is complete for the inventory below. This does **not** mean every output
is conformant: #86 and #95 remain tracked defects. Follow-up fixes are separate.

## Contract clauses and interpretation

The source is `docs/contracts/document-identity-conventions.md`:

- **C1, lines 10–19:** primary identity is lowercase SHA-256 of original bytes; moves preserve it, byte changes replace it. `doc_key` is secondary and not unique.
- **C2, lines 28–35:** confirmed supersession names the earlier SHA-256 and carries mechanism/detail. Matching titles, paths and numeric prefixes are insufficient. Hints are not confirmed links.
- **C3, lines 39–47:** native evidence pages are zero-based. Optional `document_ref` needs explicit text basis and, for nonempty quotes, a page agreeing with the locator. Absence remains valid legacy v1.
- **C4, lines 49–57:** document-text coverage evidence requires `document_ref` and extraction basis. Current extraction statistics are local result fields, not emitted `document_text_coverage` evidence objects.

Internal `PageText`, `Segment`, extraction/cache pages and `page_new` are not native
`evidence-object/v1` locators. One-based internal physical pages are valid if converted
at the native emission boundary. A supplied `#page=42` browser fragment is navigation
metadata, not an instruction to convert a native locator.

## Required exact-match inventory

Command, from the repository root:

```sh
rg -n 'locator|"page"|document_ref|supersedes|supersession_evidence' src/doc_lineage
```

All 23 matching source lines are individually classified below; `inventory.txt`
captures the original output. The cited tests are executed in `focused.log`.
`check_inventory.py` checks missing, extra and duplicate rows against the same query.
Run it in this inspected source snapshot; later source edits require a new audit.

| Source match | Disposition | Contract and evidence |
| --- | --- | --- |
| `src/doc_lineage/identity.py:25` | already-correct | C2: unused optional identity metadata; no confirmed edge emitted here. Actual publishers use structured evidence; `tests/test_identity.py` covers byte identity. The unused string field is not a native document_ref. |
| `src/doc_lineage/manifest.py:52` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:54` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:132` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:133` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:172` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:176` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:177` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:187` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:216` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:222` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:240` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/manifest.py:247` | already-correct | C1/C2: nullable fields, claim admission or serialization in the real-byte manifest publisher. `tests/lineage/test_supersession_evidence.py` proves explicit claims, invalid evidence rejection and revalidation; `tests/test_identity_manifest.py` proves filename-only hints. Existing #90/#91 covers the repaired instance. |
| `src/doc_lineage/emit/evidence.py:104` | already-correct | C3: argument/copy/order/output plumbing, not a separate page conversion. Caller locator is copied; authoritative page defect is the single row122 instance, existing #86/#87. `tests/emit/test_evidence_object.py` covers preserved section and authoritative order/page. |
| `src/doc_lineage/emit/evidence.py:121` | already-correct | C3: argument/copy/order/output plumbing, not a separate page conversion. Caller locator is copied; authoritative page defect is the single row122 instance, existing #86/#87. `tests/emit/test_evidence_object.py` covers preserved section and authoritative order/page. |
| `src/doc_lineage/emit/evidence.py:122` | confirmed-bug | C3: copies one-based span.page without conversion. `probe_contracts.py` observes physical page1 -> locator1; existing #86/#87 owns this instance. Existing `test_locator_carries_the_page_pointer` currently expects1. |
| `src/doc_lineage/emit/evidence.py:123` | already-correct | C3: argument/copy/order/output plumbing, not a separate page conversion. Caller locator is copied; authoritative page defect is the single row122 instance, existing #86/#87. `tests/emit/test_evidence_object.py` covers preserved section and authoritative order/page. |
| `src/doc_lineage/emit/evidence.py:137` | already-correct | C3: argument/copy/order/output plumbing, not a separate page conversion. Caller locator is copied; authoritative page defect is the single row122 instance, existing #86/#87. `tests/emit/test_evidence_object.py` covers preserved section and authoritative order/page. |
| `src/doc_lineage/lineage/families.py:46` | already-correct | C2: structured evidence propagation and explicit claim plumbing pass `tests/lineage/test_supersession_evidence.py`. Separate C1 malformed-ID admission occurs at line66, supplementary instance S2/#95; these rows do not independently validate hashes. |
| `src/doc_lineage/lineage/families.py:59` | already-correct | C2: structured evidence propagation and explicit claim plumbing pass `tests/lineage/test_supersession_evidence.py`. Separate C1 malformed-ID admission occurs at line66, supplementary instance S2/#95; these rows do not independently validate hashes. |
| `src/doc_lineage/lineage/families.py:66` | confirmed-bug | C1/C2: the caller-derived available hash set admits non-SHA256 identities. Production probe reproduces S2; exactly #95 owns this instance. Evidence admission itself remains covered by #90/#91. |
| `src/doc_lineage/lineage/families.py:92` | already-correct | C2: structured evidence propagation and explicit claim plumbing pass `tests/lineage/test_supersession_evidence.py`. Separate C1 malformed-ID admission occurs at line66, supplementary instance S2/#95; these rows do not independently validate hashes. |
| `src/doc_lineage/extract/cache.py:113` | already-correct | C3: internal extraction-cache Span page, not a native locator; round-trips without rebasing. `tests/test_extract_coverage.py` exercises fresh/disk-cache behavior; native conversion belongs at emitter #86/#87. |

## Supplemental boundary inventory

The exact query intentionally has blind spots: renamed fields, hash validation,
page anchors and functions called by the matched publishers. Follow-up searches:

```sh
rg -n 'page|DocumentRef|sha256|content_hash|evidence|supersession' src/doc_lineage/ingest.py src/doc_lineage/adapters src/doc_lineage/harvest src/doc_lineage/export src/doc_lineage/render src/doc_lineage/schema
rg -n 'confirmed_supersessions|supersession|doc_key|content_hash' src/doc_lineage
rg -n 'page|cache' src/doc_lineage/extract
```

| Instance | Disposition | Contract, observed boundary and evidence |
| --- | --- | --- |
| S1: `src/doc_lineage/supersession.py:11-51` | already-correct | C2 admission checks evidence mechanisms/detail, available pair membership, self-links, ambiguity and cycles. Current actual manifest and lineage tests `test_malformed_supplied_evidence_is_rejected`, `test_ambiguous_or_stale_content_claims_are_rejected` pass. Digest syntax is separately S2. |
| S2: `src/doc_lineage/lineage/families.py:14-21,59-67`; `src/doc_lineage/supersession.py:20-31` | confirmed-bug | C1/C2: caller-provided nonempty fake hashes populate both the available set and claims, so membership passes and an edge with invalid IDs is published. `probe_contracts.py --require-hash-conformance` deliberately fails on current production behavior; valid SHA256 and filename-only suppression controls pass. Exactly #95 owns the future regression in `tests/lineage/test_supersession_evidence.py::test_malformed_content_hashes_rejected`. No production fix bundled here. |
| S3: `src/doc_lineage/identity.py:28-30,66-85` | already-correct | C1: raw-byte hashing, stable ID equality and rename invariance pass `tests/test_identity.py::test_identity_hashes_raw_bytes_from_disk_or_supplied_content` and `test_move_changes_doc_key_but_preserves_content_identity`. |
| S4: `src/doc_lineage/identity.py:33-63` | needs-investigation | Local `manager_alpha/lpa/2024` grouping key is not the fleet `entity_ref/doc_type/as_of` shape. It is not currently emitted as native document_ref. Existing local-key tests pass; reuse as native attribution would require explicit mapping, not silent reinterpretation or mandatory adoption. |
| S5: `src/doc_lineage/ingest.py:43-53,88-117` | already-correct | C3: internal physical pages and deterministic segment IDs retain one-based pages. `tests/ingest/test_ingest_synthetic_pdf.py::test_segments_carry_page_pointers_and_stable_ids` passes. Single native conversion gap belongs to #86/#87. |
| S6: `src/doc_lineage/adapters/docling_segmenter.py:131-156,176-188` | already-correct | C3: both parsers yield one-based PageText; missing pages retain physical positions. Current offline fixture and Docling-item-boundary tests exercise the actual adapter with converter substitution. Real optional Docling execution remains unknown. |
| S7: `src/doc_lineage/extract/models.py:11-39`; `src/doc_lineage/extract/cache.py:28-59,79-119`; `src/doc_lineage/extract/__init__.py` | already-correct | C1/C3/C4: content-keyed internal page spans/cache and separate coverage counts; no native coverage evidence is emitted. `tests/test_extract_coverage.py` runs text/OCR/unreadable and cache controls. The OCR-to-ingest integration remains separately #92/#93, not a new audit fix. |
| S8: `src/doc_lineage/render/links.py:85-109` | already-correct | C3: preserves an explicit mirror page/tool fragment. Does not consume locator.page/document_ref or infer a base. `tests/render/test_triple_link_resolver.py::test_emits_three_hrefs` and portable-root/fragment tests pass; native viewer behavior is unknown. |
| S9: `src/doc_lineage/export/docx_redline.py:6-20` | already-correct | No page or supersession metadata is projected. Original/modified DOCX bytes go to local redline engine in explicit order; `tests/export/test_docx_redline.py` covers routing/error propagation. Native Word execution was not performed by this audit. |
| S10: `src/doc_lineage/export/fact_key_map.py:16-47,58-82` | already-correct | C1: emitted manifest binds original input bytes and map artifact hashes. This is an identity-join projection, explicitly not upstream provenance validation; no native pages or confirmed supersession created. `tests/export/test_fact_key_map.py` and CLI tests pass. |
| S11: `src/doc_lineage/harvest/edgar_ex10.py:229-271` | already-correct | C1: materialized exhibit bytes determine sha256/content_sha256 and manifest byte count. No native pages/document_ref/supersedes produced. `tests/harvest/test_edgar_ex10_offline.py::test_harvest_writes_mirror_compatible_manifest` and rollback tests pass; live SEC retrieval is not claimed. |
| S12: `src/doc_lineage/schema/validation.py:66-75` and synced evidence schema | needs-investigation | C3: generic JSON Schema validation enforces shape/nonfinite values, not cross-field page equality. `probe_contracts.py` demonstrates locator0/document_ref1 accepted. Current local emitter has no document_ref input. Future opt-in needs semantic equality validation; no schema or policy change made. |
| S13: `src/doc_lineage/schema/change_ledger.py:109-117`, `schema/schemas/change_ledger.schema.json:26` | already-correct | Internal page_new integer is a different ledger wire contract, not evidence-object/v1. `tests/test_schema_wire_names.py` passes. It is not licensed for direct native locator reuse. |
| S14: `src/doc_lineage/manifest.py:87-127,187-222,240-263` | already-correct | C1/C2: root-anchored bytes hashed into each row; existing annotation reuse does not resurrect prior supersedes evidence. `tests/test_identity_manifest.py` secure-scan/snapshot tests and `test_written_manifest_requires_evidence_again_on_each_scan` pass. |

## Reproduction, validation and limitations

From this repository root:

```sh
python3 -m pytest tests/emit/test_evidence_object.py tests/test_identity_manifest.py tests/lineage/test_supersession_chain.py -q
PYTHONPATH=src python3 docs/evidence/document-identity-audit/probe_contracts.py
PYTHONPATH=src python3 docs/evidence/document-identity-audit/probe_contracts.py --require-hash-conformance
python3 docs/evidence/document-identity-audit/check_inventory.py
```

- Exact acceptance suite: **71 passed**, zero skipped (`acceptance.log`).
- Broader named boundary suite: **242 passed**, zero skipped, two environment warnings (`focused.log`); exact command in evidence README.
- API observations (`probes.json`): physical-page-one locator1; invalid hash edge published; valid SHA256 assertion publishes; filename-only chain suppressed; schema-only contradictory pages accepted.
- The hash conformance command is an **expected RED**, exposing #95 rather than claiming it is fixed. `hash-conformance-red.log` captures the failure.
- Inventory negative control: remove one exact-match row from the report, run the checker and require nonzero; restore byte-identical report, require GREEN. `inventory-red-green.log` captures both and the restored SHA256. No production code mutation was needed for this docs-only materialization.
- `proof-bindings.json` binds inspected source bytes and all published proof files to hashes. The inventory completeness gate checks reporting coverage, not every semantic judgment; API probes and named production-path tests provide the separate behavior evidence.

Unknown: real optional Docling behavior, real OCR accuracy, native Word/PDF viewer
navigation, authentic external SEC responses, and future hosted/provider acceptance.
No hosted/server delivery is introduced. Legacy evidence without document_ref is
permitted; missing optional attribution is not itself a confirmed bug. The report
does not assert that internal library keys already satisfy the optional native shape.
