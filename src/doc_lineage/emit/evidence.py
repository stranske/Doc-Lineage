"""Emit ``evidence-object/v1`` records at the manifest boundary.

The backplane contract lives in
``docs/contracts/schemas/evidence-object-v1.schema.json`` and is consumed here,
not re-declared: every object this module builds is validated against that
schema before it is returned, so a run either produces conformant evidence or
raises. ``method`` and ``excerpt`` are the two fields the fleet's other repos
omit, so neither is optional decoration here.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from doc_lineage.identity import sha256_bytes
from doc_lineage.schema.validation import load_contract_schema, validate_contract_record

EVIDENCE_SCHEMA_VERSION = "evidence-object/v1"
EVIDENCE_SCHEMA_NAME = "evidence-object-v1"
EVIDENCE_DIRNAME = "evidence"
TRUNCATION_SUFFIX = "..."


@lru_cache(maxsize=1)
def _evidence_schema_constraints() -> tuple[frozenset[str], int]:
    """Return ``(method enum, excerpt maxLength)`` from the consumed contract."""
    schema = load_contract_schema(EVIDENCE_SCHEMA_NAME)
    methods = frozenset(schema["properties"]["method"]["enum"])
    max_chars = schema["properties"]["excerpt"]["maxLength"]
    return methods, max_chars


EVIDENCE_METHODS, EXCERPT_MAX_CHARS = _evidence_schema_constraints()


@runtime_checkable
class Span(Protocol):
    """The shape of a segment span this module can attribute.

    Declared structurally so ``doc_lineage.ingest`` can depend on ``emit``
    without ``emit`` depending back on ``ingest``.
    """

    @property
    def segment_id(self) -> str: ...

    @property
    def page(self) -> int: ...

    @property
    def order(self) -> int: ...

    @property
    def text(self) -> str: ...


def bound_excerpt(text: str, *, limit: int = EXCERPT_MAX_CHARS) -> str:
    """Return ``text`` clipped to ``limit`` characters, marking any truncation."""
    if limit < len(TRUNCATION_SUFFIX) + 1:
        raise ValueError(f"excerpt limit must exceed the truncation marker, got {limit}")
    if len(text) <= limit:
        return text
    return text[: limit - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX


def _evidence_id_preimage(
    *, source_id: str, fact_ref: str, method: str, excerpt: str | None
) -> str:
    """Serialize preimage fields with unambiguous boundaries and null encoding."""
    return json.dumps(
        {
            "excerpt": excerpt,
            "fact_ref": fact_ref,
            "method": method,
            "source_id": source_id,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def evidence_id_for(*, source_id: str, fact_ref: str, method: str, excerpt: str | None) -> str:
    """Return a deterministic id for one evidence link.

    The same source, fact, method and excerpt always yield the same id, so a
    re-run overwrites its own evidence instead of accumulating duplicates.
    """
    preimage = _evidence_id_preimage(
        source_id=source_id, fact_ref=fact_ref, method=method, excerpt=excerpt
    )
    return sha256_bytes(preimage.encode("utf-8"))[:32]


def emit_evidence_object(
    span: Span,
    *,
    source_id: str,
    method: str,
    fact_ref: str | None = None,
    excerpt: str | None = None,
    locator: dict[str, Any] | None = None,
    confidence: float | None = None,
    entity_ref: str | None = None,
) -> dict[str, Any]:
    """Build a validated ``evidence-object/v1`` payload for one span.

    ``excerpt`` defaults to the span's own text (bounded), because at the
    manifest boundary the span IS the quoted source text. The key is always
    present in the result, which is what the contract requires.
    """
    if method not in EVIDENCE_METHODS:
        raise ValueError(f"method must be one of {sorted(EVIDENCE_METHODS)}, got {method!r}")
    if not source_id:
        raise ValueError("source_id must be a non-empty string")

    resolved_fact_ref = fact_ref or f"segment:{span.segment_id}"
    resolved_excerpt = bound_excerpt(span.text if excerpt is None else excerpt)
    resolved_locator: dict[str, Any] = dict(locator) if locator else {}
    resolved_locator["page"] = span.page
    resolved_locator["order"] = span.order

    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": evidence_id_for(
            source_id=source_id,
            fact_ref=resolved_fact_ref,
            method=method,
            excerpt=resolved_excerpt,
        ),
        "fact_ref": resolved_fact_ref,
        "source_id": source_id,
        "method": method,
        "excerpt": resolved_excerpt,
        "locator": resolved_locator,
    }
    if confidence is not None:
        payload["confidence"] = confidence
    if entity_ref is not None:
        payload["entity_ref"] = entity_ref

    validate_contract_record(EVIDENCE_SCHEMA_NAME, payload)
    return payload
