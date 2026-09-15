"""Extraction cache keyed by content identity and page number."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from doc_lineage.extract.models import Span


class ExtractCache:
    """Side store keyed by ``stable_id`` and page number, never by path."""

    def __init__(self, root: Path | None = None) -> None:
        self._memory: dict[tuple[str, int], list[Span]] = {}
        self._root = root

    def get(self, stable_id: str, page: int) -> list[Span] | None:
        key = (stable_id, page)
        if key in self._memory:
            return list(self._memory[key])
        if self._root is None:
            return None
        path = self._page_path(stable_id, page)
        if not path.exists():
            return None
        from doc_lineage.extract.models import Span

        payload = json.loads(path.read_text(encoding="utf-8"))
        spans = [
            Span(
                text=item["text"],
                page=item["page"],
                bbox=tuple(item["bbox"]) if item["bbox"] is not None else None,
                source=item["source"],
            )
            for item in payload
        ]
        self._memory[key] = spans
        return list(spans)

    def put(self, stable_id: str, page: int, spans: list[Span]) -> None:
        key = (stable_id, page)
        self._memory[key] = list(spans)
        if self._root is None:
            return
        path = self._page_path(stable_id, page)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([asdict(span) for span in spans], indent=2),
            encoding="utf-8",
        )

    def _page_path(self, stable_id: str, page: int) -> Path:
        assert self._root is not None
        return self._root / stable_id / f"page-{page}.json"
