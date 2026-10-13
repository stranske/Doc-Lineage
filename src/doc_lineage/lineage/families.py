"""Document-family detection and supersession-chain construction."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from doc_lineage.identity import normalized_supersession_group, parse_numeric_prefix
from doc_lineage.supersession import SupersessionClaims, confirmed_supersessions


@dataclass(frozen=True)
class DocumentRef:
    """Minimal document reference for lineage grouping."""

    filename: str
    content_hash: str
    entity_slug: str
    category: str
    as_of: str


@dataclass(frozen=True)
class FamilyId:
    """Stable family identifier derived from library location and basename."""

    entity_slug: str
    category: str
    supersession_group: str

    def as_key(self) -> str:
        return f"{self.entity_slug}/{self.category}/{self.supersession_group}"


@dataclass(frozen=True)
class SupersessionEdge:
    """Directed edge from an older document to its successor."""

    prior_hash: str
    successor_hash: str
    prior_filename: str
    successor_filename: str
    numeric_prefix: int | None
    convention: str | None
    supersession_evidence: dict[str, str]


def detect_family(doc: DocumentRef) -> FamilyId:
    """Detect the document family for one library document."""
    return FamilyId(
        entity_slug=doc.entity_slug,
        category=doc.category,
        supersession_group=normalized_supersession_group(doc.filename),
    )


def build_supersession_chain(
    docs: Sequence[DocumentRef], *, supersession_evidence: SupersessionClaims | None = None
) -> list[SupersessionEdge]:
    """Publish only explicit content-bound claims; filenames remain family hints.

    Evidence may connect renamed documents or override filename ordering. Duplicate
    byte versions share an identity and use a deterministic representative path.
    All supplied content hashes and claim endpoints must be lowercase SHA-256
    digests, including records without a claim. Callers own original-byte provenance.
    """
    confirmed = confirmed_supersessions(supersession_evidence, {doc.content_hash for doc in docs})
    by_hash: dict[str, DocumentRef] = {}
    for doc in sorted(docs, key=lambda item: (item.filename, item.as_of)):
        by_hash.setdefault(doc.content_hash, doc)

    def chain_order(successor_hash: str) -> tuple[int, str]:
        depth = 0
        current = successor_hash
        while current in confirmed:
            depth += 1
            current = confirmed[current][0]
        return depth, successor_hash

    edges: list[SupersessionEdge] = []
    for successor_hash in sorted(confirmed, key=chain_order):
        prior_hash, evidence = confirmed[successor_hash]
        prior, successor = by_hash[prior_hash], by_hash[successor_hash]
        prefix, _, convention = parse_numeric_prefix(Path(successor.filename).name)
        edges.append(
            SupersessionEdge(
                prior_hash=prior_hash,
                successor_hash=successor_hash,
                prior_filename=prior.filename,
                successor_filename=successor.filename,
                numeric_prefix=prefix,
                convention=convention,
                supersession_evidence=dict(evidence),
            )
        )
    return edges
