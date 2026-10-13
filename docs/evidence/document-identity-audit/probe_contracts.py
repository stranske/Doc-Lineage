"""Reproduce audited semantics without changing production code or using services.

Run from the repository root with PYTHONPATH=src. --require-conformance exits
nonzero for confirmed defects; the default prints observations for the report.
"""

import argparse
import json
from dataclasses import asdict

from doc_lineage.emit import emit_evidence_object
from doc_lineage.ingest import Segment
from doc_lineage.lineage.families import DocumentRef, build_supersession_chain
from doc_lineage.schema.validation import validate_contract_record


def observations():
    span = Segment("audit-page-one", 1, 1, "Original source quotation", 25, 3)
    evidence = emit_evidence_object(span, source_id="a" * 64, method="text")
    invalid_docs = [
        DocumentRef("1_old.pdf", "hash-old", "alpha", "reports", "2026"),
        DocumentRef("2_new.pdf", "hash-new", "alpha", "reports", "2026"),
    ]
    claim = {"mechanism": "owner_assertion", "detail": "Synthetic dated assertion 2026-10-13"}
    try:
        edges = build_supersession_chain(
            invalid_docs, supersession_evidence={("hash-old", "hash-new"): claim}
        )
        invalid_hash_result = {"rejected": False, "edges": [asdict(edge) for edge in edges]}
    except ValueError:
        invalid_hash_result = {"rejected": True, "edges": []}
    good_docs = [
        DocumentRef("1_old.pdf", "a" * 64, "alpha", "reports", "2026"),
        DocumentRef("2_new.pdf", "b" * 64, "alpha", "reports", "2026"),
    ]
    good_edges = build_supersession_chain(
        good_docs, supersession_evidence={("a" * 64, "b" * 64): claim}
    )
    assert len(good_edges) == 1 and good_edges[0].supersession_evidence == claim
    assert build_supersession_chain(good_docs) == []
    contradictory = dict(evidence)
    contradictory["locator"] = {"page": 0}
    contradictory["document_ref"] = {
        "sha256": "a" * 64,
        "doc_key": "manager:alpha/legal_document/2026-10-13",
        "doc_type": "legal_document",
        "text_basis": "native",
        "page": 1,
    }
    try:
        validate_contract_record("evidence-object-v1", contradictory)
        mismatch_accepted = True
    except ValueError:
        mismatch_accepted = False
    return {
        "physical_page_one_locator": evidence["locator"]["page"],
        "expected_physical_page_one_locator": 0,
        "invalid_lineage_hashes": invalid_hash_result,
        "valid_hash_claim_published": True,
        "filename_only_claim_suppressed": True,
        "schema_only_validator_accepts_page_mismatch": mismatch_accepted,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-conformance", action="store_true")
    parser.add_argument("--require-hash-conformance", action="store_true")
    args = parser.parse_args()
    result = observations()
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_conformance:
        assert result["physical_page_one_locator"] == 0, "known #86 emitter page defect"
    if args.require_conformance or args.require_hash_conformance:
        assert result["invalid_lineage_hashes"]["rejected"], "lineage accepted non-SHA256 IDs"
