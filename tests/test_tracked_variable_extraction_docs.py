"""Pin Doc-Lineage extraction coverage docs against Workflows sync wipes.

Issue #111 / PR #128 added an ``## Extraction coverage`` section to the shared
``tracked-variable-v1`` contract. A later consumer sync from Workflows deleted
that domain-owned section while README and fact-key-map links still pointed at
``#extraction-coverage``. This gate fails closed if the section disappears again.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = REPO_ROOT / "docs" / "contracts" / "tracked-variable-v1.md"
HEADING = "## Extraction coverage"


def _extraction_section(text: str) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == HEADING), None)
    if start is None:
        raise AssertionError(f"{CONTRACT.relative_to(REPO_ROOT)} missing {HEADING!r}")
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return "\n".join(lines[start:end]).rstrip()


def test_extraction_coverage_section_documents_supported_and_unresolved_behavior() -> None:
    section = _extraction_section(CONTRACT.read_text(encoding="utf-8"))
    for required in (
        "legal.fees.management_rate",
        "extract-variables",
        "--entity-ref",
        "unresolved.json",
        "equal to X% of aggregate Capital Commitments",
        "during the Commitment Period, and Y% of invested capital thereafter",
        "no asserted record",
        "variable_id",
        "document:<original SHA-256>",
    ):
        assert required in section, f"extraction coverage must document {required!r}"


def test_readme_and_fact_key_map_anchors_resolve_to_extraction_coverage() -> None:
    anchor = "tracked-variable-v1.md#extraction-coverage"
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    fact_map = (REPO_ROOT / "docs" / "fact-key-map.md").read_text(encoding="utf-8")
    assert anchor in readme
    assert anchor in fact_map
    # Markdown heading anchors are derived from the heading text; keep both in sync.
    assert HEADING == "## Extraction coverage"
    assert _extraction_section(CONTRACT.read_text(encoding="utf-8")).startswith(HEADING)


def test_deliberate_break_missing_extraction_coverage_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sync wipe of the domain section must fail this gate, not ship silently."""
    original = CONTRACT.read_text(encoding="utf-8")
    section = _extraction_section(original)
    wiped = original.replace(section + "\n", "", 1).replace(section, "", 1)
    assert HEADING not in wiped

    contracts = tmp_path / "docs" / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "tracked-variable-v1.md").write_text(wiped, encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.REPO_ROOT", tmp_path)
    monkeypatch.setattr(f"{__name__}.CONTRACT", contracts / "tracked-variable-v1.md")

    with pytest.raises(AssertionError, match="Extraction coverage"):
        test_extraction_coverage_section_documents_supported_and_unresolved_behavior()
