"""Command line entry point for Doc-Lineage."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from doc_lineage.export import export_docx_redline
from doc_lineage.export.fact_key_map import export_fact_key_map
from doc_lineage.harvest import harvest_edgar_ex10
from doc_lineage.ingest import ingest_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doc-lineage", description="Document lineage tooling.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser(
        "ingest",
        help="Parse and segment one document, writing an artifact-manifest/v1 run directory.",
    )
    ingest.add_argument("path", type=Path, help="Document to ingest.")
    ingest.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory to write segments.json and artifact-manifest.json into.",
    )
    ingest.add_argument("--run-id", default=None, help="Override the generated run id.")
    ingest.add_argument("--git-sha", default=None, help="Record the git sha for this run.")
    ingest.add_argument(
        "--no-docling",
        action="store_true",
        help="Force the offline text backend even when Docling is importable.",
    )

    # Resolved against main on 2026-09-17. The branch had rewritten this module as a `click`
    # group, which would have removed `ingest` (merged since this branch opened) and added a
    # dependency the repo does not otherwise use. The command it contributes is added here in
    # the module's existing idiom instead, so both capabilities survive the merge.
    export = subparsers.add_parser(
        "export-docx",
        help="Write a DOCX containing native Word tracked changes between two documents.",
    )
    export.add_argument("--original", type=Path, required=True, help="Baseline DOCX.")
    export.add_argument("--modified", type=Path, required=True, help="Revised DOCX.")
    export.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the redline. Defaults to stdout.",
    )
    export.add_argument(
        "--author",
        default="Doc-Lineage",
        help="Author attributed to the tracked changes.",
    )
    export.add_argument(
        "--blackline",
        action="store_true",
        help="Required acknowledgement that a tracked-changes comparison is being produced.",
    )

    fact_map = subparsers.add_parser(
        "export-fact-key-map",
        help="Export tracked-variable identity joins and an artifact manifest.",
    )
    fact_map.add_argument("path", type=Path, help="JSON array of tracked-variable/v1 records.")
    fact_map.add_argument("--output", type=Path, required=True, help="New run directory to create.")

    harvest = subparsers.add_parser(
        "harvest-edgar",
        help="Harvest SEC EX-10 exhibits for one CIK into a mirror-compatible manifest.",
    )
    harvest.add_argument("--cik", required=True, help="SEC CIK (zero-padded or bare digits).")
    harvest.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory to write artifact-manifest.json into.",
    )
    harvest.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Recorded filing JSON for offline harvest (no live SEC calls).",
    )
    return parser


def _run_export_docx(args: argparse.Namespace) -> int:
    if not args.blackline:
        print("doc-lineage export-docx: --blackline is required", file=sys.stderr)
        return 1
    try:
        redline = export_docx_redline(
            args.original.read_bytes(),
            args.modified.read_bytes(),
            author=args.author,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"doc-lineage export-docx: {exc}", file=sys.stderr)
        return 1
    if args.output is None:
        sys.stdout.buffer.write(redline)
    else:
        args.output.write_bytes(redline)
        print(f"blackline: {args.output}")
    return 0


def _run_harvest_edgar(args: argparse.Namespace) -> int:
    try:
        result = harvest_edgar_ex10(
            args.cik,
            args.output,
            fixture_path=args.fixture,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"doc-lineage harvest-edgar: {exc}", file=sys.stderr)
        return 1
    print(
        f"harvested {len(result.exhibits)} EX-10 exhibit(s) for CIK {result.cik} "
        f"-> {result.manifest_path}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export-fact-key-map":
        try:
            manifest = export_fact_key_map(args.path, args.output)
        except (OSError, ValueError) as exc:
            print(f"doc-lineage export-fact-key-map: {exc}", file=sys.stderr)
            return 1
        print(f"manifest: {manifest}")
        return 0
    if args.command == "export-docx":
        return _run_export_docx(args)
    if args.command == "harvest-edgar":
        return _run_harvest_edgar(args)
    if args.command != "ingest":  # pragma: no cover - argparse rejects anything else
        raise AssertionError(f"unhandled command: {args.command}")

    try:
        result = ingest_document(
            args.path,
            output_dir=args.output,
            run_id=args.run_id,
            git_sha=args.git_sha,
            allow_docling=not args.no_docling,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"doc-lineage ingest: {exc}", file=sys.stderr)
        return 1

    print(
        f"ingested {result.source_path.name} "
        f"[backend={result.backend} run_id={result.run_id}] -> "
        f"{len(result.segments)} segment(s) across {result.page_count} page(s)"
    )
    print(f"manifest: {result.manifest_path}")
    print(f"segments: {result.segments_path}")
    if result.pages_without_text_layer:
        pages = ", ".join(str(page) for page in result.pages_without_text_layer)
        print(f"warning: no text layer on page(s) {pages}; recognition fallback required")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via the console script
    raise SystemExit(main())
