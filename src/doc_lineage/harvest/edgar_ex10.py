"""Harvest SEC EX-10 exhibits for public legal lineage."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = "artifact-manifest/v1"
TOOL_NAME = "doc-lineage-harvest-edgar"
MANIFEST_FILENAME = "artifact-manifest.json"
_EX10_TYPE = re.compile(r"^EX-10(?:\.\d+)?$", re.IGNORECASE)
_MIN_REQUEST_INTERVAL_SECONDS = 0.2
_last_request_at: float | None = None


@dataclass(frozen=True)
class Ex10Exhibit:
    """One EX-10 exhibit discovered in an SEC filing."""

    sequence: str
    exhibit_type: str
    description: str
    document_url: str
    accession_number: str
    filing_date: str

    def artifact_id(self, cik: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.description.lower()).strip("-")[:48]
        return f"edgar-{cik.lstrip('0')}-ex10-{self.sequence}-{slug or 'exhibit'}"


@dataclass(frozen=True)
class HarvestResult:
    """Artifacts written by one harvest run."""

    cik: str
    output_dir: Path
    manifest_path: Path
    exhibits: tuple[Ex10Exhibit, ...]


def parse_ex10_exhibits(filing: dict[str, Any]) -> list[Ex10Exhibit]:
    """Return EX-10 exhibits from a recorded SEC filing payload."""
    documents = filing.get("documents")
    if not isinstance(documents, list):
        raise ValueError("filing payload must include a documents list")

    accession = str(filing.get("accession_number", ""))
    filing_date = str(filing.get("filing_date", ""))
    exhibits: list[Ex10Exhibit] = []
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise ValueError(f"documents[{index}] must be an object")
        exhibit_type = str(document.get("type", "")).strip()
        if not _EX10_TYPE.match(exhibit_type):
            continue
        sequence = str(document.get("sequence", index + 1))
        description = str(document.get("description", "")).strip()
        document_url = str(document.get("document_url", "")).strip()
        if not description or not document_url:
            raise ValueError(
                f"documents[{index}] EX-10 exhibit must include description and document_url"
            )
        exhibits.append(
            Ex10Exhibit(
                sequence=sequence,
                exhibit_type=exhibit_type.upper(),
                description=description,
                document_url=document_url,
                accession_number=accession,
                filing_date=filing_date,
            )
        )
    return exhibits


def _rate_limit() -> None:
    global _last_request_at
    now = time.monotonic()
    if _last_request_at is not None:
        elapsed = now - _last_request_at
        if elapsed < _MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
    _last_request_at = time.monotonic()


def _load_filing_from_edgar(cik: str) -> dict[str, Any]:
    try:
        from edgar import Company
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "edgartools is required for live SEC harvest; install doc-lineage[harvest]"
        ) from exc

    normalized = cik.strip().lstrip("0") or "0"
    _rate_limit()
    company = Company(normalized)
    _rate_limit()
    filings = company.get_filings(form="10-K").head(1)
    if not filings:
        raise ValueError(f"no 10-K filings found for CIK {cik}")
    filing = filings[0]
    documents: list[dict[str, str]] = []
    for attachment in filing.attachments:
        doc_type = str(getattr(attachment, "document_type", "") or "")
        if not _EX10_TYPE.match(doc_type):
            continue
        documents.append(
            {
                "sequence": str(getattr(attachment, "sequence", len(documents) + 1)),
                "type": doc_type,
                "description": str(getattr(attachment, "description", "") or doc_type),
                "document_url": str(getattr(attachment, "url", "") or ""),
            }
        )
    return {
        "cik": str(getattr(filing, "cik", normalized)),
        "accession_number": str(getattr(filing, "accession_number", "")),
        "filing_date": str(getattr(filing, "filing_date", "")),
        "documents": documents,
    }


def _build_manifest(cik: str, exhibits: list[Ex10Exhibit]) -> dict[str, Any]:
    created_at = datetime.now(tz=UTC).isoformat()
    artifacts: list[dict[str, Any]] = []
    for exhibit in exhibits:
        registration_digest = hashlib.sha256(exhibit.document_url.encode("utf-8")).hexdigest()
        artifacts.append(
            {
                "artifact_id": exhibit.artifact_id(cik),
                "name": exhibit.description,
                "kind": "data",
                "path": (
                    f"harvest/edgar/{cik.lstrip('0') or '0'}/"
                    f"{exhibit.accession_number}/{exhibit.sequence}.pdf"
                ),
                "sha256": registration_digest,
                "bytes": 0,
                "media_type": "application/pdf",
                "doc_type_id": "edgar_ex10_lpa",
                "source_url": exhibit.document_url,
                "content_sha256": registration_digest,
                "provenance": {
                    "schema_version": "document-mirror/v1",
                    "cik": cik,
                    "accession_number": exhibit.accession_number,
                    "filing_date": exhibit.filing_date,
                    "exhibit_type": exhibit.exhibit_type,
                    "sequence": exhibit.sequence,
                },
            }
        )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": f"doc-lineage-harvest-edgar/{cik}/{created_at}",
        "tool": TOOL_NAME,
        "git_sha": None,
        "created_at": created_at,
        "artifacts": artifacts,
    }


def harvest_edgar_ex10(
    cik: str,
    output_dir: Path,
    *,
    fixture_path: Path | None = None,
) -> HarvestResult:
    """Harvest EX-10 exhibits for one CIK and register mirror-compatible artifacts."""
    if fixture_path is not None:
        filing = json.loads(fixture_path.read_text(encoding="utf-8"))
    else:
        filing = _load_filing_from_edgar(cik)

    exhibits = parse_ex10_exhibits(filing)
    if not exhibits:
        raise ValueError(f"no EX-10 exhibits found for CIK {cik}")

    manifest = _build_manifest(cik, exhibits)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return HarvestResult(
        cik=cik,
        output_dir=output_dir,
        manifest_path=manifest_path,
        exhibits=tuple(exhibits),
    )
