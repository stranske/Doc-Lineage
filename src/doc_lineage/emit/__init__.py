"""Emitters for the backplane contracts this repo produces."""

from doc_lineage.emit.evidence import (
    EVIDENCE_DIRNAME,
    EVIDENCE_METHODS,
    EVIDENCE_SCHEMA_NAME,
    EVIDENCE_SCHEMA_VERSION,
    EXCERPT_MAX_CHARS,
    Span,
    bound_excerpt,
    emit_evidence_object,
    evidence_id_for,
)

__all__ = [
    "EVIDENCE_DIRNAME",
    "EVIDENCE_METHODS",
    "EVIDENCE_SCHEMA_NAME",
    "EVIDENCE_SCHEMA_VERSION",
    "EXCERPT_MAX_CHARS",
    "Span",
    "bound_excerpt",
    "emit_evidence_object",
    "evidence_id_for",
]
