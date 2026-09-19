"""Document-family detection and supersession-chain construction."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from doc_lineage.identity import normalized_supersession_group, parse_numeric_prefix


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


def detect_family(doc: DocumentRef) -> FamilyId:
    """Detect the document family for one library document."""
    return FamilyId(
        entity_slug=doc.entity_slug,
        category=doc.category,
        supersession_group=normalized_supersession_group(doc.filename),
    )


def build_supersession_chain(docs: Sequence[DocumentRef]) -> list[SupersessionEdge]:
    """Build supersession edges using content-hash identity and numeric-prefix ordering."""
    grouped: dict[str, list[DocumentRef]] = {}
    for doc in docs:
        family = detect_family(doc)
        grouped.setdefault(family.as_key(), []).append(doc)

    edges: list[SupersessionEdge] = []
    for family_docs in grouped.values():
        ordered = sorted(
            family_docs,
            key=lambda item: (
                parse_numeric_prefix(item.filename)[0] or 0,
                item.as_of,
                item.filename,
            ),
        )
        for prior, successor in zip(ordered, ordered[1:], strict=False):
            prefix, _, convention = parse_numeric_prefix(successor.filename)
            edges.append(
                SupersessionEdge(
                    prior_hash=prior.content_hash,
                    successor_hash=successor.content_hash,
                    prior_filename=prior.filename,
                    successor_filename=successor.filename,
                    numeric_prefix=prefix,
                    convention=convention,
                )
            )
    return edges
