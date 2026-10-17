# Persisted ingest consumer audit — source #113

This is an audit-only delivery of [#113](https://github.com/stranske/Doc-Lineage/issues/113),
not an implementation of either missing public transition. Initial reviewed main was
`45971929b534d953e1c56ffb42b4bdfc3fd4b994`. During the audit, PR #128 merged as
`aa2351f72636e76f80b4e0013e9a099b2d9a495b` (2026-10-17T12:21:56Z). The audit was
rebased independently onto that **final reviewed main/base**, and every final
`src/` byte remains identical to it. Initial-base probes and test outcomes are
retained with their own source bindings; current-main legal consumption is
separately replayed successfully through three fresh public CLI processes. The historical proposal inspected `6591255c3b32b2d2a7ff010a417358689640f873`;
its later readback was `b9daca70b27f452d62d8c6ccdb3bcd3b5dc7a783`. Those are historical
provenance, not claims about current main. The current blackline hash is still
`c339f553462d1437ee512e07ef5a20a401779dedf703c904534b3003f907afd7`.

The original meta-candidate remains **unilateral**: Codex retained the narrowed
turn-2 inventory after Claude proposed no meta-candidate. Claude supplied no
counterevidence to the two independently traced instances; that is not mutual
agreement on an architecture or on giving every library a command. The owner
accepted this bounded audit separately (F12, brief `current-54-oct15-2026-v1`,
scope SHA-256 `615624fcb7c6de0876ca338cbdbe646f68d741f8c2b0e096506f6e786e8a1719`).

## Boundary and enumeration rule

Start with README's blackline, lineage and extracted tracked-variable outputs,
its persisted ingest publisher, interoperability paragraph, and explicit links to
fact-map export and static provenance links. Follow their local production callers
and their directly referenced contracts. The inventory below includes every entry
in that bounded route: segment/evidence publication, section construction/pairing,
mutation composition, legal/report-section claim production, identity-map export,
Mosaic evidence joins, vocabulary adoption, adopted ledger wire models and provenance navigation. It records
local controls separately from sibling adoption. Tests/search matches nominate
paths; actual calls and artifact probes establish the dispositions.

Raw-PDF extraction/cache, corpus manifests/supersession and catalog loading are
adjacent documented paths, not consumers of persisted ingest artifacts. They are
listed to make the boundary explicit. Native DOCX-package replay is excluded and
belongs to [#110 / PR #127](https://github.com/stranske/Doc-Lineage/pull/127).
No general CLI inventory, semantic matching, hosted service, schema migration,
new issues, follow-up PRs, workflow edits or architecture changes are authorized.
The target environment supports local Python and static artifacts; this delivery
requires no Office application, native helper, OCR engine or computer-wide prompt.

## Complete bounded inventory

Rows I3/I5 describe the **initial reviewed main** where the two gaps were traced.
At final reviewed main `aa2351f`, I5 is **confirmed working for the documented
management-rate subset**: `cli.main` → `publish_variables` → `load_ingest` →
`ingest._extract_verified` validates the source/manifest/segments/evidence, then
publishes claims/evidence/source bytes to a fresh directory. The new current-main
control feeds those actual records through I7 and checks the source digest,
schema, rates, evidence reference, zero-based page and all artifact hashes.
Current legal replay and the full suite are independently executed here; all
25 vocabulary keys and arbitrary legal interpretation remain outside this proof.
I3 remains owned, unmerged work in PR #129 at this snapshot.

“Confirmed” means locally traced/observed, not provider or sibling acceptance.
“Intentional” identifies a documented contract boundary. “UNKNOWN” means the
necessary caller or acceptance evidence is not available within this repo.

| Entry and contract | Producer → actual consumer/caller | Identity and restart/replay evidence | Disposition |
| --- | --- | --- | --- |
| I1. Persisted segments and quoted evidence; README Ingest, `artifact-manifest/v1`, `evidence-object/v1`, document-identity conventions | `cli.main` ingest branch → `ingest_document` → `segment_pages`, `build_evidence_objects` → `emit_evidence_object`; manifests list `segments.json` and every evidence file | Original PDF digest; segment IDs use digest prefix/page/order. Manifest hashes/sizes bind bytes. Evidence binds full source digest, `segment:<id>`, bounded excerpt, method and zero-based locator. New test and copied control independently reread all manifested bytes; fresh child receives only disk paths. | **Confirmed working publisher/control.** Publication is not a validated downstream loader. Legacy evidence lacks optional `document_ref`, intentionally valid under v1. Main does not retain original PDF bytes in the ingest directory. |
| I2. Numbered section library and edge serialization; README blackline intent, `blackline.py` | `mutations.detect.detect_change_classes` → `_segments_from_payload` → `build_section_tree` → `align_sections`; optional `emit_lineage_edges_ndjson` serializes decisions | Builder accepts caller-supplied `source_sha256` and `Segment` objects; no hash authentication. `Section.segment_ids` retains membership, but emitted edge rows contain section IDs/titles/confidence, not source hashes or evidence refs. Real before/after PDFs reload and pair IDs 1/2 with only fee changed. | **Confirmed working library/control**, not a persisted comparison artifact or evidence validator. Ambiguous/unmatched handling already has positive tests. |
| I3. Persisted ingest → supported validated section-comparison/reopen transition | I1 publisher → `load_segment_tree` can JSON-decode → I2 typed composition; `cli.main` has no pairing branch on reviewed main | Passing the actual persisted path to `build_section_tree` raises TypeError. Exact `pair-sections --help` exits 2. Forged source/segment identity passed through the real `detect_change_classes` caller still returns `gate_provision_change`; caller never loads a manifest/evidence file. No immutable comparison/replay record is published by that composition. | **Confirmed missing public transition on reviewed main; owned by F11 [#112 / ready PR #129](https://github.com/stranske/Doc-Lineage/pull/129)**. Do not duplicate the repair. Missing-command observation is supporting evidence, not the premise for requiring a CLI. |
| I4. Synthetic mutation ground truth | `tools/generate_mutations.py` → fixture segment JSON → `load_segment_tree`/`detect_change_classes`; invoked by `tests/mutations/test_mutation_pair_known_diff.py` | Synthetic identities and labeled fee mutation are fixture bindings, not original-PDF provenance. JSON loader performs no schema/hash validation. New real-PDF regression also exercises the same production composition, avoiding an exclusively authored-segment control. | **Intentional synthetic test surface**, not a general persisted-ingest validator. Its identity trust boundary is included in I3, not a separate issue. |
| I5. Legal source text/evidence → tracked-variable claims; README extracted clauses, tracked-variable spec, 25-key legal vocabulary | I1 publishes segments/evidence only. Existing next consumer is `cli.main` export-fact-key-map branch → `export_fact_key_map` → `build_fact_key_map`, which requires already-authored records | Actual I1 `segments.json` is rejected by the exporter: “tracked-variable input must be a JSON array.” An evidence object has source/segment/method/quote/page, but lacks asserted claim/value/entity and dual provenance anchors. `extract-variables --help` exits 2. Initial main has no production call constructing those claims; final main adds the bounded validated caller described above. | **Confirmed missing on initial main; now repaired on final main for the narrow management-rate subset (actual current replay passes); owned by F10 [#111 / ready PR #128](https://github.com/stranske/Doc-Lineage/pull/128)**. The exporter correctly rejects the wrong artifact; extraction belongs upstream. |
| I6. Consultant/report-section tracked-variable family | README existing consultant tracker/crosswalk intent and tracked-variable contract identify Doc-Lineage + Inv-Man-Intake as `report_section` owners | Contract defines wire shape and ownership. Local `compare.classify.classify_segment` consumes caller-authored `SegmentPair` text and returns materiality/classification, not asserted claim/evidence records. There is no documented report-section extraction invocation/grammar or identified sibling production ingest reader in this bounded source. | **UNKNOWN delivery/adoption**, not a confirmed new missing command or a silently completed extraction feature. Human must define concrete input/consumer acceptance before calling it an uncovered gap. |
| I7. Tracked-variable identity map → Mosaic join | Authored `tests/fixtures/fact_key_map/tracked_variables.json` → public `export_fact_key_map`; `docs/fact-key-map.md` and Mosaic contract specify downstream join | Requires wire version, nonempty `variable_id`/`ontology_key`/canonical `entity_ref`, optional nonempty period; rejects conflicting duplicate IDs. Fresh output directory, deterministic JSON and manifested hash/size. Probe reloads actual exported file/manifest; 27 exporter tests cover entity/period separation, replay/determinism/rejection. | **Confirmed working projection; intentionally excludes extraction/evidence validation. UNKNOWN actual sibling consumption.** Contract requires `(ontology_key, entity_ref, period)`; absent period is not a wildcard. |
| I8. Claim/evidence → Mosaic facts/evidence reference closure | I7 emits identity joins; `docs/contracts/mosaic-core-v1.md` assigns record/bundle layout and cross-artifact reference checks to the consumer | Consumer must check evidence existence, claim association, locator and entity/period normalization. Doc-Lineage's exporter neither accepts evidence bundles nor emits Mosaic facts. No sibling runtime was inspected/executed here. | **Intentional ownership boundary; sibling runtime/restart is UNKNOWN.** Shared schema text alone does not establish a live downstream ingest or a confirmed gap in this repo. |
| I9. Tracked-variable provenance → static document/mirror/source links | Documented Python caller passes a tracked-variable mapping → `render.resolve_triple_link` in `render/links.py`; actual callers are render tests | Validates required navigation fields, traversal-safe relative blob path and HTTP(S) source URL; escapes output, keeps supplied page fragment. Tests reread authored JSON, parse actual HTML destinations and exercise absent/unsafe source data. Raw I1 evidence fails “provenance must be an object,” as it should. | **Confirmed working helper on authored inputs; intentional caller projection; confirmed current-main producer/consumer mismatch H2 on actual legal output.** It does not select manifest source refs, validate evidence, access files or render a full view. Browser navigation and the downstream renderer remain UNKNOWN. I5 owns legal claim/anchor production. |
| I10. Shared ontology keys for Inv-Man-Intake, Manager-Database, Pension-Data | README interoperability → `vocab.load_legal_clauses` → packaged JSON; called by vocabulary tests | Loader uses package resources and rejects duplicate JSON keys; tests check key set/schema semantics, wheel/install access. This publishes identifiers, not extracted claims or sibling adoption. | **Confirmed working vocabulary publication; intentionally not extraction. UNKNOWN sibling adoption/restart.** |
| I11. Adopted change/continuity/persistence/stale-flag/crosswalk/material-change wire models; README comparison-tools paragraph | `schema/change_ledger.py` defines six `*Row.from_wire`/`to_wire` models; `test_schema_wire_names.py` loads authored consultant/legal JSON into real row constructors and validators | Named wire fields, enum/finite/nonnegative numeric checks, and material-ledger `From`/`To` round trip are exercised by the full suite. These rows carry human section/year/page/text coordinates, not authenticated ingest source/evidence bindings. No local production ingest caller is identified for the calculation of continuity, persistence or stale flags. | **Confirmed schema/round-trip controls; UNKNOWN persisted-ingest production handoff.** README commits to adopting existing field names; it does not define the computation or a public report-section extraction transition. Not a newly classified missing API. |

### Adjacent routes deliberately not promoted into gaps

README's `extract`/`ExtractCache` API reads original documents and its own cache;
it does not load `segments.json`. Existing extraction tests cover disk reloads.
Corpus `write_manifest` and `build_supersession_chain` read originals and explicit
content-bound evidence, not I1 segment evidence. Their rules intentionally do not
infer supersession from paired sections. Comparison catalog loaders read package
resources and take `SegmentPair` values; no documented automatic claim-production
contract was found. Deliverable-Render owns rendering; output-substrate and
Mosaic specs assign bundle layout/import to consumers. A shared run contract does
not imply that this ingest command emits `run.json` or that every library requires
a command. These are boundary/UNKNOWN entries, not additional classified gaps.

## Exact missing-transition checks and working controls

`docs/evidence/issue-113/probe_base.py` executes the actual publisher and actual
production readers/callers against a source-hash-bound base. The captured
`probes/observations.json` records arguments' artifact context and exact errors,
including the invalid identities accepted by I4. This is a revision-bound probe,
not a unit test asserting APIs stay absent. It is deliberately bound to the
initial base; reconstruct that source revision in a disposable copy for replay
(see the evidence README). On a changed production tree it
refuses the old audit premise. The positive regression remains valid when the
owned implementations land; it requires only the established library behavior.

`test_persisted_pdf_ingest_replays_existing_production_pairing` generates two real,
distinct two-page PDFs with reportlab, forces the actual offline PDF parser,
publishes segments/evidence/manifests, verifies their hashes/source/page bindings,
and starts a fresh Python process with only persisted paths. That child calls
`load_segment_tree`, `detect_change_classes`, `build_section_tree`, `align_sections`
and the edge emitter. Assertions require IDs 1/2, section-ID methods, only the fee
changed, exact segment membership, distinct source digests, and
`gate_provision_change`. No mocked parser/segment list or API implemented by #129
is used. The original synthetic LPA is separately ingested by the bounded probes;
it is not silently substituted with the easier control fixture.

The actual mutation replaces exactly one header-parser call in production
`src/doc_lineage/blackline.py` with `None`. The unchanged regression fails with
`AssertionError: PERSISTED_INGEST_PAIRING_DISCONNECTED`. Exact original bytes are
restored in `finally`, the test hash stays unchanged, and the same test passes.
`mutation.json`, genuine RED/GREEN JUnit/logs and the executable recipe record this
causal boundary. It demonstrates an existing working control, **not a production
repair**. Audit-only authority precludes bundling a fix: #111/#112 already own the
two approved implementations, and any additional format/policy changes require
a human decision. Final production identity is independently checked against base.

## Additional observations returned only for human decision

H1 — **Confirmed format limitation; expectation/repair decision unresolved.**
On the original `synthetic_lpa.pdf`, offline ingest emits one flattened segment
per page. Page 1 starts with the title, so `_parse_section_header` (anchored at
start) ignores sections 1/2; page 2 begins with section 3 and keeps section 4
inside its text. I2 constructs only ID 3. Replacing `1.75%` with `2.00%` in the
actual persisted page-1 payload and invoking `detect_change_classes` yields `()`.
This probe is an intentionally edited text projection, **not a second PDF with
valid source identity**. The separate two-PDF control proves the working shape.
Contract: README promises page segments and section comparison; builder docstring
requires numbered headers. Whether the product must split inline headings in
this backend, warn on coverage, or retain the current grammar needs an owner
decision. The unchanged header grammar in the latest observed PR #129 snapshot
`03538527f4329cdee6fa65dd965fc3ce8efdc79a` inherits that behavior;
PR #128's narrow extraction grammar handles its own inline clause boundaries.
No automatic issue or fix was created. Confidence is high in the observed loss,
not in any unstated universal PDF-layout obligation.

H2 — **Confirmed additional missing legal-output → navigation transition on final main; report only.**
The actual `replay_legal.py` output is passed unchanged to the documented
`resolve_triple_link(tracked_variable)` consumer. Producer
`publish_variables` → `ingest._extract_verified` emits `provenance.mirror` with
`mirror_root: "."`, `blob_path: "source/synthetic_lpa.pdf"`, `page_anchor: "#page=1"`.
The record validates as `tracked-variable/v1` and the copied source exists under
the emitted claims directory. Consumer `render.links._mirror_url` passes the
root to `_relative_path`, which rejects the `.` component, so no HTML is emitted:
`ValueError: mirror_root must be a relative POSIX path without traversal`.
`probe_current.py` invokes that real consumer on the actual published record and
captures claim/evidence hashes, identity, provenance and failure. This is not a
name-search finding or an authored-record substitute. Contract: the static-link
doc explicitly accepts tracked-variable provenance and relative mirror roots;
its authored-fixture controls pass, but the current producer's relative-root
convention does not compose. Confidence is high in this exact mismatch. A human
must choose consistent producer/consumer path policy before any repair; no source,
shared schema, issue or follow-up PR was changed/created. It is not hidden inside
the already-delivered extraction or section-pairing repairs. The probe records
an outcome and does not assert that the failure must persist after a future fix.

H3 — **UNKNOWN report-section and sibling adoption.** I6/I8/I10 name contracts and
owners, but provide no inspected sibling production/restart evidence here. A
human can select a concrete report-section input/output and actual consumer for
future assessment. This audit does not turn search absence into a confirmed gap.

## Immutable owned implementations versus main

Read-only Git-object inspection of PR #128 at
`acf58d2f2a909252ab98883b884eb03a1d27513b` shows a validated persisted-ingest
reader, source/evidence validation and bounded management-rate claims with
unresolved outcomes. That is narrower than all 25 keys or consultant extraction.
PR #129 at `d0ef0da712a0152d27707f0fdd55696eaad4f98c` adds validated retained
originals, ordered source/segment/manifest/options identity, immutable comparison
IDs and replay revalidation. PR #129 advanced through `aecb5f3b80b79df9b9681033e287c6af16d31636` to
`03538527f4329cdee6fa65dd965fc3ce8efdc79a` during the audit; its current writer/branch is preserved. These are **owned
implementations**. PR #129 remains unmerged and its new public APIs were not executed by this
audit. PR #128 subsequently merged into final reviewed main; its legal public
pipeline was independently replayed by this audit, with final-base full-suite
evidence. Historical PR-declared results are linked rather than silently
substituted for those actual executions.
PR #127's DOCX package fidelity and ID lookup remain separate. No other worktree,
claim or payload was edited; no hosted runner was dispatched.

See the [evidence receipt](../evidence/issue-113/README.md) for actual commands,
results, limitations, source/test/fixture bindings, portable artifacts and writer
gate receipts. No merge, source closure, provider PASS or sibling acceptance is
claimed by this delivery.
