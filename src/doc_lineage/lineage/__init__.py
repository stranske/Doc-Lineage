"""Document-family detection and supersession chains."""

from doc_lineage.lineage.families import (
    DocumentRef,
    FamilyId,
    SupersessionEdge,
    build_supersession_chain,
    detect_family,
)

__all__ = [
    "DocumentRef",
    "FamilyId",
    "SupersessionEdge",
    "build_supersession_chain",
    "detect_family",
]
