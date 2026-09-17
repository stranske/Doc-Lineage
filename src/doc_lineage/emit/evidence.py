"""Emit ``evidence-object/v1`` records at the manifest boundary.

The backplane contract lives in
``docs/contracts/schemas/evidence-object-v1.schema.json`` and is consumed here,
not re-declared: every object this module builds is validated against that
schema before it is returned, so a run either produces conformant evidence or
raises. ``method`` and ``excerpt`` are the two fields the fleet's other repos
omit, so neither is optional decoration here.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from doc_lineage.identity import sha256_bytes
from doc_lineage.schema.validation import validate_contract_record

EVIDENCE_SCHEMA_VERSION = "evidence-object/v1"
EVIDENCE_SCHEMA_NAME = "evidence-object-v1"
EVIDENCE_DIRNAME = "evidence"

#: ``maxLength`` of ``excerpt`` in the contract schema. Longer source text is
#: truncated rather than dropped, because a missing excerpt is the exact gap
#: this contract exists to close.
EXCERPT_MAX_CHARS = 2000
TRUNCATION_SUFFIX = "..."

#: The ``method`` enum from the contract schema.
EVIDENCE_METHODS = frozenset(
    {
        "rule",
        "parser",
        "table",
        "text",
        "ocr",
        "llm",
        "computed",
        "fallback",
        "manual",
    }
)

_ID_FIELD_SEPARATOR = "|"
_ABSENT_EXCERPT_TOKEN = "<absent>"


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


def evidence_id_for(*, source_id: str, fact_ref: str, method: str, excerpt: str | None) -> str:
    """Return a deterministic id for one evidence link.

    The same source, fact, method and excerpt always yield the same id, so a
    re-run overwrites its own evidence instead of accumulating duplicates.
    """
    excerpt_part = _ABSENT_EXCERPT_TOKEN if excerpt is None else excerpt
    parts = (source_id, fact_ref, method, excerpt_part)
    return sha256_bytes(_ID_FIELD_SEPARATOR.join(parts).encode("utf-8"))[:32]


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
    resolved_locator: dict[str, Any] = {"page": span.page, "order": span.order}
    if locator:
        resolved_locator.update(locator)

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
