"""Supersession-chain construction tests."""

from doc_lineage.identity import sha256_bytes
from doc_lineage.lineage.families import DocumentRef, build_supersession_chain, detect_family


def test_detect_family_groups_numeric_prefix_variants() -> None:
    doc = DocumentRef(
        filename="02-terms.pdf",
        content_hash=sha256_bytes(b"version-b"),
        entity_slug="manager_alpha",
        category="lpa",
        as_of="2025",
    )
    family = detect_family(doc)
    assert family.supersession_group == "terms"


def test_build_supersession_chain_orders_by_numeric_prefix() -> None:
    docs = [
        DocumentRef("01-terms.pdf", sha256_bytes(b"version-a"), "manager_alpha", "lpa", "2024"),
        DocumentRef("02-terms.pdf", sha256_bytes(b"version-b"), "manager_alpha", "lpa", "2025"),
        DocumentRef("03-terms.pdf", sha256_bytes(b"version-c"), "manager_alpha", "lpa", "2026"),
    ]
    assert build_supersession_chain(docs) == []
    edges = build_supersession_chain(
        docs,
        supersession_evidence={
            (sha256_bytes(b"version-a"), sha256_bytes(b"version-b")): {
                "mechanism": "owner_assertion",
                "detail": "Owner, 2026-10-13",
            },
            **(
                {
                    (sha256_bytes(b"version-b"), sha256_bytes(b"version-c")): {
                        "mechanism": "source_metadata",
                        "detail": "Version notice",
                    }
                }
                if any(doc.content_hash == sha256_bytes(b"version-c") for doc in docs)
                else {}
            ),
        },
    )
    assert len(edges) == 2
    assert edges[0].prior_hash == sha256_bytes(b"version-a")
    assert edges[0].successor_hash == sha256_bytes(b"version-b")
    assert edges[1].prior_hash == sha256_bytes(b"version-b")
    assert edges[1].successor_hash == sha256_bytes(b"version-c")
    assert edges[0].numeric_prefix == 2


def test_nested_paths_use_numeric_order_and_skip_duplicate_hashes() -> None:
    docs = [
        DocumentRef(
            "folder/10-terms.pdf", sha256_bytes(b"version-c"), "manager_alpha", "lpa", "2026"
        ),
        DocumentRef(
            "folder/2-terms.pdf", sha256_bytes(b"version-b"), "manager_alpha", "lpa", "2026"
        ),
        DocumentRef(
            "folder/1-terms.pdf", sha256_bytes(b"version-a"), "manager_alpha", "lpa", "2026"
        ),
        DocumentRef(
            "folder/3-terms.pdf", sha256_bytes(b"version-b"), "manager_alpha", "lpa", "2026"
        ),
    ]
    assert build_supersession_chain(docs) == []
    edges = build_supersession_chain(
        docs,
        supersession_evidence={
            (sha256_bytes(b"version-a"), sha256_bytes(b"version-b")): {
                "mechanism": "owner_assertion",
                "detail": "Owner, 2026-10-13",
            },
            **(
                {
                    (sha256_bytes(b"version-b"), sha256_bytes(b"version-c")): {
                        "mechanism": "source_metadata",
                        "detail": "Version notice",
                    }
                }
                if any(doc.content_hash == sha256_bytes(b"version-c") for doc in docs)
                else {}
            ),
        },
    )
    assert [(edge.prior_hash, edge.successor_hash) for edge in edges] == [
        (sha256_bytes(b"version-a"), sha256_bytes(b"version-b")),
        (sha256_bytes(b"version-b"), sha256_bytes(b"version-c")),
    ]


def test_build_supersession_chain_deduplicates_non_adjacent_repeated_hashes() -> None:
    docs = [
        DocumentRef("01-terms.pdf", sha256_bytes(b"version-a"), "manager_alpha", "lpa", "2024"),
        DocumentRef("02-terms.pdf", sha256_bytes(b"version-b"), "manager_alpha", "lpa", "2025"),
        DocumentRef("03-terms.pdf", sha256_bytes(b"version-a"), "manager_alpha", "lpa", "2026"),
    ]
    assert build_supersession_chain(docs) == []
    edges = build_supersession_chain(
        docs,
        supersession_evidence={
            (sha256_bytes(b"version-a"), sha256_bytes(b"version-b")): {
                "mechanism": "owner_assertion",
                "detail": "Owner, 2026-10-13",
            },
            **(
                {
                    (sha256_bytes(b"version-b"), sha256_bytes(b"version-c")): {
                        "mechanism": "source_metadata",
                        "detail": "Version notice",
                    }
                }
                if any(doc.content_hash == sha256_bytes(b"version-c") for doc in docs)
                else {}
            ),
        },
    )
    assert [(edge.prior_hash, edge.successor_hash) for edge in edges] == [
        (sha256_bytes(b"version-a"), sha256_bytes(b"version-b")),
    ]
