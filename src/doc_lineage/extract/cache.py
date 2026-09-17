"""Extraction cache keyed by content identity, page number and recognition mode."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from doc_lineage.extract.models import Span

#: Recognition modes, ordered weakest first. A cached *empty* page recorded under a
#: weaker mode must not satisfy a later read under a stronger one, or one
#: recognition-disabled run would permanently pin the page as unreadable.
OCRMode = Literal["off", "ocr", "office"]

_MODE_STRENGTH: dict[str, int] = {"off": 0, "ocr": 1, "office": 1}


class ExtractCache:
    """Side store keyed by ``stable_id`` and page number, never by path."""

    def __init__(self, root: Path | None = None) -> None:
        self._memory: dict[tuple[str, int], tuple[str, list[Span]]] = {}
        self._root = root

    def get(self, stable_id: str, page: int, mode: OCRMode = "off") -> list[Span] | None:
        """Return cached spans, or ``None`` when this read is a miss.

        An entry that recorded *no* spans is an "unreadable" outcome, and that
        outcome is only valid for reads whose recognition mode is no stronger
        than the one that produced it.
        """
        key = (stable_id, page)
        entry = self._memory.get(key)
        if entry is None:
            entry = self._read_disk(stable_id, page)
            if entry is not None:
                self._memory[key] = entry
        if entry is None:
            return None

        cached_mode, spans = entry
        if not spans and _MODE_STRENGTH.get(mode, 0) > _MODE_STRENGTH.get(cached_mode, 0):
            return None
        return list(spans)

    def put(self, stable_id: str, page: int, spans: list[Span], mode: OCRMode = "off") -> None:
        self._memory[(stable_id, page)] = (mode, list(spans))
        if self._root is None:
            return
        path = self._page_path(stable_id, page)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ocr_mode": mode,
            "spans": [asdict(span) for span in spans],
        }
        self._write_atomic(path, json.dumps(payload, indent=2))

    def _read_disk(self, stable_id: str, page: int) -> tuple[str, list[Span]] | None:
        if self._root is None:
            return None
        path = self._page_path(stable_id, page)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            return self._parse_payload(json.loads(raw))
        except (ValueError, TypeError, KeyError):
            # Malformed or truncated cache data is a miss, never a hard failure:
            # the caller re-extracts and `put` overwrites the bad entry.
            return None

    @staticmethod
    def _parse_payload(payload: object) -> tuple[str, list[Span]]:
        from doc_lineage.extract.models import Span

        if isinstance(payload, dict):
            mode = str(payload["ocr_mode"])
            items = payload["spans"]
        else:
            # Legacy on-disk format: a bare list of spans with no recorded mode.
            # Treat it as the strongest mode so a non-empty entry still hits, and
            # an empty one is re-checked whenever recognition is enabled.
            mode = "off"
            items = payload
        if not isinstance(items, list):
            raise TypeError("cached spans payload is not a list")
        spans = [
            Span(
                text=item["text"],
                page=item["page"],
                bbox=tuple(item["bbox"]) if item["bbox"] is not None else None,
                source=item["source"],
            )
            for item in items
        ]
        return mode, spans

    @staticmethod
    def _write_atomic(path: Path, text: str) -> None:
        """Write via a temp file in the same directory, then rename into place.

        The cache root is shared, so a concurrent reader must never observe a
        half-written JSON file.
        """
        handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def _page_path(self, stable_id: str, page: int) -> Path:
        assert self._root is not None
        return self._root / stable_id / f"page-{page}.json"
