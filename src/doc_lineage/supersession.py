"""Validate explicit, content-bound supersession claims for local publishers."""

from __future__ import annotations

import re
from collections.abc import Mapping, Set

SupersessionClaims = Mapping[tuple[str, str], Mapping[str, object]]
MECHANISMS = frozenset({"source_metadata", "content_comparison", "owner_assertion"})


def _validate_content_hash(digest: str) -> None:
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("supersession content identities must be lowercase SHA-256 digests")


def confirmed_supersessions(
    claims: SupersessionClaims | None, available_hashes: Set[str]
) -> dict[str, tuple[str, dict[str, str]]]:
    """Return successor -> (prior, evidence), rejecting invalid or ambiguous claims.

    Pair keys bind assertions to original content, independently of filename rank.
    No claims means no confirmed lineage. Validate all inputs before publication.
    Digest syntax does not prove that a caller hashed the original bytes.
    """
    for digest in available_hashes:
        _validate_content_hash(digest)

    confirmed: dict[str, tuple[str, dict[str, str]]] = {}
    for pair, evidence in (claims or {}).items():
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("supersession claims require (prior_hash, successor_hash) keys")
        prior, successor = pair
        _validate_content_hash(prior)
        _validate_content_hash(successor)
        if prior == successor:
            raise ValueError("a document cannot supersede its own content identity")
        if prior not in available_hashes or successor not in available_hashes:
            raise ValueError("supersession claim references unavailable document content")
        if not isinstance(evidence, Mapping):
            raise ValueError("supersession evidence must contain mechanism and detail")
        mechanism, detail = evidence.get("mechanism"), evidence.get("detail")
        if not isinstance(mechanism, str) or mechanism not in MECHANISMS:
            raise ValueError("unknown or missing supersession evidence mechanism")
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError("supersession evidence detail must be a nonempty string")
        if successor in confirmed:
            raise ValueError("a successor cannot have multiple confirmed predecessors")
        confirmed[successor] = (prior, {"mechanism": mechanism, "detail": detail})

    for successor in confirmed:
        seen: set[str] = set()
        current = successor
        while current in confirmed:
            if current in seen:
                raise ValueError("supersession claims must not form a cycle")
            seen.add(current)
            current = confirmed[current][0]
    return confirmed
