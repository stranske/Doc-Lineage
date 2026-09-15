"""Command-line interface for doc-lineage."""

import sys
from pathlib import Path

import click

from doc_lineage.export import export_docx_redline


@click.group()
@click.version_option(package_name="doc_lineage")
def cli() -> None:
    """Document lineage and blackline engine."""
    pass


@cli.command(name="export-docx")
@click.option(
    "--original",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to the original DOCX file.",
)
@click.option(
    "--modified",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to the modified DOCX file.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to write the output DOCX file. Defaults to stdout.",
)
@click.option(
    "--author",
    type=str,
    default="Doc-Lineage",
    help="Author name for tracked changes.",
)
@click.option(
    "--blackline",
    is_flag=True,
    default=False,
    help="Generate a blackline (tracked changes) comparison.",
)
def export_docx(
    original: Path, modified: Path, output: Path | None, author: str, blackline: bool
) -> None:
    """Export DOCX comparison with tracked changes."""
    if not blackline:
        click.echo("Error: --blackline flag is required for export-docx", err=True)
        sys.exit(1)

    # Read input files
    original_bytes = original.read_bytes()
    modified_bytes = modified.read_bytes()

    # Generate redline
    redline = export_docx_redline(original_bytes, modified_bytes, author=author)

    # Write output
    if output:
        output.write_bytes(redline)
        click.echo(f"Blackline written to {output}")
    else:
        sys.stdout.buffer.write(redline)


def main() -> None:
    """Entry point for the doc-lineage CLI."""
    cli()


if __name__ == "__main__":
    main()
