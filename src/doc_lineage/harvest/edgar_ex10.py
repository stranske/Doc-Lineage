"""Harvest SEC EX-10 exhibits for public legal lineage."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

MANIFEST_SCHEMA_VERSION = "artifact-manifest/v1"
MANIFEST_SCHEMA_NAME = "artifact-manifest-v1"
TOOL_NAME = "doc-lineage-harvest-edgar"
MANIFEST_FILENAME = "artifact-manifest.json"
_EX10_TYPE = re.compile(r"^EX-10(?:\.\d+)?$", re.IGNORECASE)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MIN_REQUEST_INTERVAL_SECONDS = 0.2
_SEC_USER_AGENT = (
    "stranske Doc-Lineage harvest/0.1 "
    "(doc-lineage-harvest-edgar; https://github.com/stranske/Doc-Lineage)"
)
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

    def doc_type_id(self) -> str:
        description = self.description.lower()
        if "side letter" in description:
            return "edgar_ex10_side_letter"
        if "limited partnership" in description or re.search(r"\blpa\b", description):
            return "edgar_ex10_lpa"
        return "edgar_ex10_exhibit"


@dataclass(frozen=True)
class HarvestResult:
    """Artifacts written by one harvest run."""

    cik: str
    output_dir: Path
    manifest_path: Path
    exhibits: tuple[Ex10Exhibit, ...]


def _validate_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized or not _SAFE_IDENTIFIER.match(normalized):
        raise ValueError(f"{field_name} must be a non-empty safe identifier")
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise ValueError(f"{field_name} must not contain path separators or traversal")
    return normalized


def _artifact_extension(document_url: str) -> str:
    suffix = PurePosixPath(urlparse(document_url).path).suffix.lower()
    return suffix if suffix else ".bin"


def _media_type_for_extension(extension: str) -> str:
    if extension in {".htm", ".html"}:
        return "text/html"
    if extension == ".pdf":
        return "application/pdf"
    if extension == ".txt":
        return "text/plain"
    return "application/octet-stream"


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
        raw_sequence = document.get("sequence", index + 1)
        raw_description = document.get("description")
        raw_document_url = document.get("document_url")
        if raw_sequence is None or raw_description is None or raw_document_url is None:
            raise ValueError(
                f"documents[{index}] EX-10 exhibit must include sequence, description, and document_url"
            )
        sequence = str(raw_sequence)
        description = str(raw_description).strip()
        document_url = str(raw_document_url).strip()
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


def _resolve_fixture_exhibit_path(fixture_dir: Path, document_url: str) -> Path:
    local_name = PurePosixPath(urlparse(document_url).path).name
    if (
        not local_name
        or local_name in {".", ".."}
        or "/" in local_name
        or "\\" in local_name
    ):
        raise ValueError(f"invalid fixture local name derived from {document_url}")
    resolved_dir = fixture_dir.resolve()
    local_path = (resolved_dir / local_name).resolve()
    if not local_path.is_relative_to(resolved_dir):
        raise ValueError(f"fixture path escapes fixture_dir: {local_path}")
    return local_path


def _fetch_exhibit_bytes(
    exhibit: Ex10Exhibit,
    *,
    fixture_dir: Path | None,
) -> bytes:
    if fixture_dir is not None:
        local_path = _resolve_fixture_exhibit_path(fixture_dir, exhibit.document_url)
        if not local_path.is_file():
            raise ValueError(
                f"fixture exhibit content missing for {exhibit.document_url}: {local_path}"
            )
        return local_path.read_bytes()

    _rate_limit()
    request = urllib.request.Request(
        exhibit.document_url,
        headers={"User-Agent": _SEC_USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"HTTP {exc.code} fetching {exhibit.document_url}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"failed to fetch {exhibit.document_url}: {exc.reason}"
        ) from exc
    except (TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"network error fetching {exhibit.document_url}: {exc}"
        ) from exc


def _artifact_relative_path(cik: str, exhibit: Ex10Exhibit, extension: str) -> str:
    normalized_cik = _validate_identifier(cik.lstrip("0") or "0", "cik")
    accession = _validate_identifier(exhibit.accession_number, "accession_number")
    sequence = _validate_identifier(exhibit.sequence, "sequence")
    return f"harvest/edgar/{normalized_cik}/{accession}/{sequence}{extension}"


def _build_manifest(
    cik: str,
    exhibits: list[Ex10Exhibit],
    materialized: list[tuple[Ex10Exhibit, Path, bytes]],
) -> dict[str, Any]:
    created_at = datetime.now(tz=UTC).isoformat()
    artifacts: list[dict[str, Any]] = []
    for exhibit, artifact_path, content in materialized:
        content_digest = hashlib.sha256(content).hexdigest()
        extension = artifact_path.suffix.lower()
        artifacts.append(
            {
                "artifact_id": exhibit.artifact_id(cik),
                "name": exhibit.description,
                "kind": "data",
                "path": _artifact_relative_path(cik, exhibit, extension),
                "sha256": content_digest,
                "bytes": len(content),
                "media_type": _media_type_for_extension(extension),
                "doc_type_id": exhibit.doc_type_id(),
                "source_url": exhibit.document_url,
                "content_sha256": content_digest,
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
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": f"doc-lineage-harvest-edgar/{cik}/{created_at}",
        "tool": TOOL_NAME,
        "git_sha": None,
        "created_at": created_at,
        "artifacts": artifacts,
    }
    from doc_lineage.schema.validation import validate_contract_record

    validate_contract_record(MANIFEST_SCHEMA_NAME, manifest)
    return manifest


def harvest_edgar_ex10(
    cik: str,
    output_dir: Path,
    *,
    fixture_path: Path | None = None,
) -> HarvestResult:
    """Harvest EX-10 exhibits for one CIK and register mirror-compatible artifacts."""
    if fixture_path is not None:
        filing = json.loads(fixture_path.read_text(encoding="utf-8"))
        fixture_dir = fixture_path.parent
    else:
        filing = _load_filing_from_edgar(cik)
        fixture_dir = None

    exhibits = parse_ex10_exhibits(filing)
    if not exhibits:
        raise ValueError(f"no EX-10 exhibits found for CIK {cik}")

    output_dir.mkdir(parents=True, exist_ok=True)
    materialized: list[tuple[Ex10Exhibit, Path, bytes]] = []
    for exhibit in exhibits:
        content = _fetch_exhibit_bytes(exhibit, fixture_dir=fixture_dir)
        extension = _artifact_extension(exhibit.document_url)
        relative_path = _artifact_relative_path(cik, exhibit, extension)
        artifact_path = output_dir / relative_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(content)
        materialized.append((exhibit, artifact_path, content))

    manifest = _build_manifest(cik, exhibits, materialized)
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
