"""Supersession-chain construction tests."""

from doc_lineage.lineage.families import DocumentRef, build_supersession_chain, detect_family


def test_detect_family_groups_numeric_prefix_variants() -> None:
    doc = DocumentRef(
        filename="02-terms.pdf",
        content_hash="hash-b",
        entity_slug="manager_alpha",
        category="lpa",
        as_of="2025",
    )
    family = detect_family(doc)
    assert family.supersession_group == "terms"


def test_build_supersession_chain_orders_by_numeric_prefix() -> None:
    docs = [
        DocumentRef("01-terms.pdf", "hash-a", "manager_alpha", "lpa", "2024"),
        DocumentRef("02-terms.pdf", "hash-b", "manager_alpha", "lpa", "2025"),
        DocumentRef("03-terms.pdf", "hash-c", "manager_alpha", "lpa", "2026"),
    ]
    edges = build_supersession_chain(docs)
    assert len(edges) == 2
    assert edges[0].prior_hash == "hash-a"
    assert edges[0].successor_hash == "hash-b"
    assert edges[1].prior_hash == "hash-b"
    assert edges[1].successor_hash == "hash-c"
    assert edges[0].numeric_prefix == 2
