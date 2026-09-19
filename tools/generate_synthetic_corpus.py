"""Generate paired before/after segment trees with labeled ground truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "tests" / "fixtures" / "synthetic_corpus"


def _case(
    case_id: str,
    prior_segments: dict[str, str],
    current_segments: dict[str, str],
    expected: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "prior_segments": prior_segments,
        "current_segments": current_segments,
        "expected": expected,
    }


def build_manifest() -> dict[str, Any]:
    """Return the synthetic corpus manifest with non-zero labeled cases."""
    cases = [
        _case(
            "verbatim_fee_terms",
            {"fee_terms": "The management fee is 1.5% per annum."},
            {"fee_terms": "The management fee is 1.5% per annum."},
            [{"section_id": "fee_terms", "change_type": "VERBATIM", "tier": "T3"}],
        ),
        _case(
            "near_verbatim_punctuation",
            {"reporting": "Reports are delivered each quarter to investors."},
            {"reporting": "Reports are delivered quarterly to investors."},
            [{"section_id": "reporting", "change_type": "NEAR_VERBATIM", "tier": "T3"}],
        ),
        _case(
            "revised_investment_policy",
            {
                "investment_policy": (
                    "The fund may invest up to 25% in private placements with board approval."
                )
            },
            {
                "investment_policy": (
                    "The fund may not invest in private placements without LP consent and a 60-day notice."
                )
            },
            [{"section_id": "investment_policy", "change_type": "REVISED", "tier": "T1"}],
        ),
        _case(
            "new_risk_disclosure",
            {},
            {"risk_disclosure": "Counterparty concentration risk is monitored monthly."},
            [{"section_id": "risk_disclosure", "change_type": "NEW", "tier": "T1"}],
        ),
        _case(
            "unknown_absence_without_signal",
            {"legacy_clause": "Legacy side-letter rights remain in force."},
            {},
            [{"section_id": "legacy_clause", "change_type": "UNKNOWN_ABSENCE", "tier": "T2"}],
        ),
    ]
    return {"version": 1, "cases": cases}


def write_corpus(output_root: Path = OUTPUT_ROOT) -> Path:
    """Write paired segment trees and ``ground_truth.json`` under ``output_root``."""
    manifest = build_manifest()
    output_root.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        case_dir = output_root / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "prior_segments.json").write_text(
            json.dumps(case["prior_segments"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (case_dir / "current_segments.json").write_text(
            json.dumps(case["current_segments"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    manifest_path = output_root / "ground_truth.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_ROOT,
        help="Directory for generated corpus fixtures",
    )
    args = parser.parse_args()
    path = write_corpus(args.output)
    print(path)


if __name__ == "__main__":
    main()
