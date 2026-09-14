"""Exercise CLI argument handling and binary output independently of the engine."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from doc_lineage.cli import cli, main


@pytest.mark.parametrize("to_file", [True, False], ids=["file", "stdout"])
def test_export_docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, to_file: bool) -> None:
    original = tmp_path / "original.docx"
    modified = tmp_path / "modified.docx"
    output = tmp_path / "redline.docx"
    original.write_bytes(b"original package")
    modified.write_bytes(b"modified package")
    redline = b"PK\x00\xff\r\nredline package"
    export = Mock(return_value=redline)
    monkeypatch.setattr("doc_lineage.cli.export_docx_redline", export)
    args = ["export-docx", "--original", str(original), "--modified", str(modified), "--blackline"]
    if to_file:
        args.extend(["--output", str(output), "--author", "Counsel"])

    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 0, result.output
    export.assert_called_once_with(
        b"original package", b"modified package", author="Counsel" if to_file else "Doc-Lineage"
    )
    if to_file:
        assert output.read_bytes() == redline
        assert f"Blackline written to {output}" in result.output
    else:
        assert result.stdout_bytes == redline
        assert not output.exists()
    assert original.read_bytes() == b"original package"
    assert modified.read_bytes() == b"modified package"


def test_export_requires_blackline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = tmp_path / "original.docx"
    modified = tmp_path / "modified.docx"
    original.write_bytes(b"original package")
    modified.write_bytes(b"modified package")
    export = Mock()
    monkeypatch.setattr("doc_lineage.cli.export_docx_redline", export)

    result = CliRunner().invoke(
        cli, ["export-docx", "--original", str(original), "--modified", str(modified)]
    )

    assert result.exit_code == 1
    assert "--blackline flag is required" in result.stderr
    export.assert_not_called()


def test_main_runs_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    command = Mock()
    monkeypatch.setattr("doc_lineage.cli.cli", command)

    main()

    command.assert_called_once_with()
