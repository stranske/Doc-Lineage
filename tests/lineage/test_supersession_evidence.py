"""Exercise evidence admission through actual manifest and lineage publishers."""

import json
from pathlib import Path

import pytest

from doc_lineage.identity import sha256_bytes
from doc_lineage.lineage.families import DocumentRef, build_supersession_chain
from doc_lineage.manifest import build_manifest_rows, read_manifest, write_manifest


def _documents(root: Path) -> tuple[list[DocumentRef], str, str]:
    docs = []
    (root / "alpha/reports").mkdir(parents=True)
    # Explicit evidence can link renamed documents against numeric filename order.
    for filename, content in [("10_original.pdf", b"old"), ("2_renamed.pdf", b"new")]:
        (root / "alpha/reports" / filename).write_bytes(content)
        docs.append(DocumentRef(filename, sha256_bytes(content), "alpha", "reports", "2026"))
    return docs, docs[0].content_hash, docs[1].content_hash


@pytest.mark.parametrize("mechanism", ["owner_assertion", "source_metadata", "content_comparison"])
def test_evidence_is_preserved_by_both_publication_paths(tmp_path: Path, mechanism: str) -> None:
    docs, prior, successor = _documents(tmp_path)
    evidence = {"mechanism": mechanism, "detail": "Owner/version comparison, 2026-10-13, page 2"}
    claims = {(prior, successor): evidence}

    rows = build_manifest_rows(tmp_path, supersession_evidence=claims)
    newer = next(row for row in rows if row.sha256 == successor)
    edges = build_supersession_chain(docs, supersession_evidence=claims)
    assert json.loads(newer.to_json())["supersedes"] == prior
    assert json.loads(newer.to_json())["supersession_evidence"] == evidence
    assert [(edge.prior_hash, edge.successor_hash) for edge in edges] == [(prior, successor)]
    assert edges[0].supersession_evidence == evidence
    assert build_supersession_chain(list(reversed(docs)), supersession_evidence=claims) == edges
    evidence["detail"] = "caller changed its input"
    assert newer.supersession_evidence["detail"] != evidence["detail"]
    assert edges[0].supersession_evidence["detail"] != evidence["detail"]


@pytest.mark.parametrize("publisher", ["manifest", "lineage"])
@pytest.mark.parametrize(
    "evidence",
    [
        None,
        {},
        {"detail": "notice"},
        {"mechanism": "numeric_prefix_separator", "detail": "notice"},
        {"mechanism": [], "detail": "notice"},
        {"mechanism": "owner_assertion"},
        {"mechanism": "owner_assertion", "detail": ""},
        {"mechanism": "owner_assertion", "detail": " \n\t"},
        {"mechanism": "owner_assertion", "detail": False},
    ],
)
def test_malformed_supplied_evidence_is_rejected(tmp_path: Path, publisher: str, evidence) -> None:
    docs, prior, successor = _documents(tmp_path)
    claims = {(prior, successor): evidence}
    with pytest.raises(ValueError, match="supersession"):
        if publisher == "manifest":
            build_manifest_rows(tmp_path, supersession_evidence=claims)
        else:
            build_supersession_chain(docs, supersession_evidence=claims)


@pytest.mark.parametrize("publisher", ["manifest", "lineage"])
@pytest.mark.parametrize("kind", ["self", "unavailable", "conflict", "cycle", "bad-key"])
def test_ambiguous_or_stale_content_claims_are_rejected(
    tmp_path: Path, publisher: str, kind: str
) -> None:
    docs, prior, successor = _documents(tmp_path)
    third = sha256_bytes(b"third")
    (tmp_path / "alpha/reports/third.pdf").write_bytes(b"third")
    docs.append(DocumentRef("third.pdf", third, "alpha", "reports", "2026"))
    evidence = {"mechanism": "source_metadata", "detail": "Document version notice"}
    pairs = {
        "self": [(prior, prior)],
        "unavailable": [("missing", successor)],
        "conflict": [(prior, successor), (third, successor)],
        "cycle": [(prior, successor), (successor, prior)],
        "bad-key": ["not a pair"],
    }[kind]
    claims = dict.fromkeys(pairs, evidence)
    message = {
        "self": "own content identity",
        "unavailable": "unavailable document content",
        "conflict": "multiple confirmed predecessors",
        "cycle": "form a cycle",
        "bad-key": "require .* keys",
    }[kind]
    with pytest.raises(ValueError, match=message):
        if publisher == "manifest":
            build_manifest_rows(tmp_path, supersession_evidence=claims)
        else:
            build_supersession_chain(docs, supersession_evidence=claims)


def test_written_manifest_requires_evidence_again_on_each_scan(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    _docs, prior, successor = _documents(library)
    output = tmp_path / "manifest.jsonl"
    claims = {(prior, successor): {"mechanism": "owner_assertion", "detail": "Owner, 2026-10-13"}}
    write_manifest(library, output, supersession_evidence=claims)
    first = output.read_bytes()
    write_manifest(library, output, supersession_evidence=claims)
    assert output.read_bytes() == first
    assert json.loads(read_manifest(output)["alpha/reports/2_renamed.pdf"])["supersedes"] == prior

    write_manifest(library, output)
    assert all(json.loads(line)["supersedes"] is None for line in read_manifest(output).values())
    assert all(
        json.loads(line)["supersession_evidence"] is None for line in read_manifest(output).values()
    )
    before = output.read_bytes()
    with pytest.raises(ValueError):
        write_manifest(library, output, supersession_evidence={(prior, successor): {}})
    assert output.read_bytes() == before


def test_prefix_only_input_publishes_no_confirmed_lineage(tmp_path: Path) -> None:
    directory = tmp_path / "alpha/reports"
    directory.mkdir(parents=True)
    for name, content in [("1_report.pdf", b"old"), ("2_report.pdf", b"new")]:
        (directory / name).write_bytes(content)
    rows = build_manifest_rows(tmp_path)
    newer = next(row for row in rows if Path(row.path).name == "2_report.pdf")
    assert newer.supersedes is None
    assert newer.supersession_evidence is None
    assert newer.supersession_hint == sha256_bytes(b"old")
    docs = [DocumentRef(row.path, row.sha256, "alpha", "reports", "2026") for row in rows]
    assert build_supersession_chain(docs) == []


def test_confirmed_chain_order_follows_evidence_instead_of_hash_or_filename_order() -> None:
    docs = [
        DocumentRef("3_c.pdf", "hash-a", "alpha", "reports", "2026"),
        DocumentRef("1_a.pdf", "hash-z", "alpha", "reports", "2026"),
        DocumentRef("2_b.pdf", "hash-y", "alpha", "reports", "2026"),
    ]
    evidence = {"mechanism": "source_metadata", "detail": "Explicit version notices"}
    claims = {("hash-y", "hash-a"): evidence, ("hash-z", "hash-y"): evidence}
    edges = build_supersession_chain(docs, supersession_evidence=claims)
    assert [(edge.prior_hash, edge.successor_hash) for edge in edges] == [
        ("hash-z", "hash-y"),
        ("hash-y", "hash-a"),
    ]
