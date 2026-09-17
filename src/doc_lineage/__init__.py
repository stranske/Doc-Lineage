"""Document lineage: identity, extraction with page pointers, and version and family comparison for recurring investment documents"""

from doc_lineage.identity import DocumentIdentity, compute_identity
from doc_lineage.ingest import IngestResult, Segment, ingest_document

__version__ = "0.1.0"
__all__ = [
    "DocumentIdentity",
    "IngestResult",
    "Segment",
    "compute_identity",
    "ingest_document",
]
