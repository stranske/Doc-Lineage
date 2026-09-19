"""Exercise CLI argument handling and binary output independently of the engine.

Rewritten from `click.testing.CliRunner` to argparse on 2026-09-17, when this branch's `click`
CLI was resolved against the `argparse` CLI that had merged to main in the meantime. The
assertions are deliberately the same ones the click version made — file vs stdout output, the
author default, the `--blackline` acknowledgement, and that neither input is mutated — so the
coverage survives the interface change rather than being quietly dropped with it.
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from doc_lineage.cli import main


@pytest.mark.parametrize("to_file", [True, False], ids=["file", "stdout"])
def test_export_docx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
    to_file: bool,
) -> None:
    original = tmp_path / "original.docx"
    modified = tmp_path / "modified.docx"
    output = tmp_path / "redline.docx"
    original.write_bytes(b"original package")
    modified.write_bytes(b"modified package")
    redline = b"PK\x00\xff\r\nredline package"
    export = Mock(return_value=redline)
    monkeypatch.setattr("doc_lineage.cli.export_docx_redline", export)
    argv = ["export-docx", "--original", str(original), "--modified", str(modified), "--blackline"]
    if to_file:
        argv.extend(["--output", str(output), "--author", "Counsel"])

    exit_code = main(argv)

    assert exit_code == 0
    export.assert_called_once_with(
        b"original package", b"modified package", author="Counsel" if to_file else "Doc-Lineage"
    )
    captured = capsysbinary.readouterr()
    if to_file:
        assert output.read_bytes() == redline
        assert str(output).encode() in captured.out
    else:
        # Binary must reach stdout unaltered; a text-mode write would mangle \r\n and \xff.
        assert captured.out == redline
        assert not output.exists()
    assert original.read_bytes() == b"original package"
    assert modified.read_bytes() == b"modified package"


def test_export_requires_blackline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original = tmp_path / "original.docx"
    modified = tmp_path / "modified.docx"
    original.write_bytes(b"original package")
    modified.write_bytes(b"modified package")
    export = Mock()
    monkeypatch.setattr("doc_lineage.cli.export_docx_redline", export)

    exit_code = main(["export-docx", "--original", str(original), "--modified", str(modified)])

    assert exit_code == 1
    assert "--blackline is required" in capsys.readouterr().err
    export.assert_not_called()


def test_export_reports_engine_errors_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original = tmp_path / "original.docx"
    modified = tmp_path / "modified.docx"
    original.write_bytes(b"original package")
    modified.write_bytes(b"modified package")
    monkeypatch.setattr(
        "doc_lineage.cli.export_docx_redline",
        Mock(side_effect=ValueError("Tracked changes require a non-empty author")),
    )

    exit_code = main(
        ["export-docx", "--original", str(original), "--modified", str(modified), "--blackline"]
    )

    assert exit_code == 1
    assert "non-empty author" in capsys.readouterr().err


def test_ingest_subcommand_survived_the_merge() -> None:
    """The click rewrite would have deleted `ingest`, which had already merged to main."""
    from doc_lineage.cli import build_parser

    subcommands = build_parser()._subparsers._group_actions[0].choices

    assert "ingest" in subcommands
    assert "export-docx" in subcommands
    assert "harvest-edgar" in subcommands


def test_harvest_edgar_cli_offline_fixture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "harvest" / "edgar_ex10_filing.json"
    output = tmp_path / "harvest-out"

    exit_code = main(
        [
            "harvest-edgar",
            "--cik",
            "0001067983",
            "--output",
            str(output),
            "--fixture",
            str(fixture),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "harvested 2 EX-10 exhibit(s)" in captured.out
    manifest = json.loads((output / "artifact-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["artifacts"]) == 2


def test_harvest_edgar_cli_reports_errors_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty_fixture = tmp_path / "empty.json"
    empty_fixture.write_text(
        json.dumps(
            {
                "cik": "1",
                "accession_number": "000000001-24-000001",
                "filing_date": "2024-01-01",
                "documents": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "harvest-edgar",
            "--cik",
            "0000000001",
            "--output",
            str(tmp_path / "out"),
            "--fixture",
            str(empty_fixture),
        ]
    )

    assert exit_code == 1
    assert "no EX-10 exhibits found" in capsys.readouterr().err
