#!/usr/bin/env python3
"""Build a manifest.jsonl for a local document library tree."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from doc_lineage.manifest import write_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Root directory of the document library")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write manifest.jsonl",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    write_manifest(args.root.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
