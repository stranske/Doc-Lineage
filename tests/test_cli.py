"""Exercise CLI argument handling and binary output independently of the engine.

Rewritten from `click.testing.CliRunner` to argparse on 2026-09-17, when this branch's `click`
CLI was resolved against the `argparse` CLI that had merged to main in the meantime. The
assertions are deliberately the same ones the click version made — file vs stdout output, the
author default, the `--blackline` acknowledgement, and that neither input is mutated — so the
coverage survives the interface change rather than being quietly dropped with it.
"""

import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, Mock
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from doc_lineage.cli import main
from tests.export.test_docx_redline_golden import NS, W, _docx, _visible_text


def _comparison_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["XDG_CACHE_HOME"] = str(cwd / "engine-cache")
    return subprocess.run(
        [sys.executable, "-m", "doc_lineage.cli", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        timeout=120,
        check=False,
    )


@pytest.fixture
def comparison_inputs(tmp_path):
    original, modified = tmp_path / "original.docx", tmp_path / "modified.docx"
    original.write_bytes(_docx("The fee is five dollars."))
    modified.write_bytes(_docx("The fee is ten dollars."))
    manifest = tmp_path / "artifact-manifest.json"
    manifest.write_text('{"evidence": "retain unchanged"}\n', encoding="utf-8")
    store = tmp_path / "records"
    result = _comparison_cli(
        "create-comparison",
        "--original",
        original.name,
        "--modified",
        modified.name,
        "--comparison-store",
        str(store),
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr.decode()
    comparison_id = result.stdout.decode().strip()
    assert re.fullmatch(r"cmp_[0-9a-f]{32}", comparison_id)
    return original, modified, manifest, store, comparison_id


@pytest.mark.parametrize("by_id", [True, False], ids=["id-only", "file-pair"])
@pytest.mark.parametrize("to_file", [True, False], ids=["file", "stdout"])
def test_comparison_new_process_native_round_trip(comparison_inputs, tmp_path, by_id, to_file):
    original, modified, manifest, store, comparison_id = comparison_inputs
    record_path = store / f"{comparison_id}.json"
    preserved = {path: path.read_bytes() for path in (original, modified, manifest, record_path)}
    record = json.loads(record_path.read_text())
    assert record == {
        "schema_version": "docx-comparison/v1",
        "comparison_id": comparison_id,
        "original_path": str(original),
        "modified_path": str(modified),
        "original_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "modified_sha256": hashlib.sha256(modified.read_bytes()).hexdigest(),
    }
    elsewhere = tmp_path / "fresh-process-cwd"
    elsewhere.mkdir()
    output = elsewhere / "redline.docx"
    selection = (
        ["--blackline", comparison_id, "--comparison-store", str(store)]
        if by_id
        else ["--blackline", "--original", str(original), "--modified", str(modified)]
    )
    result = _comparison_cli(
        "export-docx",
        *selection,
        *(["--output", str(output)] if to_file else []),
        "--author",
        "Counsel",
        cwd=elsewhere,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr == b""
    if to_file:
        assert result.stdout.decode().splitlines() == [f"blackline: {output}"]
        redline = output.read_bytes()
    else:
        assert not output.exists()
        # Parse the raw stream, so a status line or text-mode corruption fails.
        assert result.stdout.startswith(b"PK\x03\x04")
        redline = result.stdout
    with ZipFile(BytesIO(redline)) as package:
        assert package.testzip() is None
        document = ET.fromstring(package.read("word/document.xml"))
    revisions = document.findall(".//w:ins", NS) + document.findall(".//w:del", NS)
    assert document.findall(".//w:ins", NS), "Expected native Word insertion markup"
    assert document.findall(".//w:del", NS), "Expected native Word deletion markup"
    assert all(node.get(f"{{{W}}}author") == "Counsel" for node in revisions)
    assert all(node.get(f"{{{W}}}id") is not None for node in revisions)
    assert _visible_text(document, "ins") == "The fee is five dollars."
    assert _visible_text(document, "del") == "The fee is ten dollars."
    assert all(path.read_bytes() == content for path, content in preserved.items())


@pytest.mark.parametrize("role", ["original", "modified"])
@pytest.mark.parametrize("to_file", [True, False], ids=["file", "stdout"])
def test_comparison_sha256_check_disconnection(comparison_inputs, tmp_path, role, to_file):
    """Named mutation gate: valid changed DOCX bytes MUST fail before publication."""
    original, modified, manifest, store, comparison_id = comparison_inputs
    source = original if role == "original" else modified
    source.write_bytes(_docx("Changed but still a valid DOCX package."))
    record_path = store / f"{comparison_id}.json"
    preserved = {path: path.read_bytes() for path in (original, modified, manifest, record_path)}
    output = tmp_path / "unchanged-output.docx"
    output.write_bytes(b"existing output must survive")
    result = _comparison_cli(
        "export-docx",
        "--blackline",
        comparison_id,
        "--comparison-store",
        str(store),
        *(["--output", str(output)] if to_file else []),
        cwd=tmp_path,
    )
    assert result.returncode != 0, "SHA256_CHECK_DISCONNECTION: changed bytes were exported"
    assert b"SHA-256 mismatch" in result.stderr
    assert result.stdout == b""
    assert output.read_bytes() == b"existing output must survive"
    assert all(path.read_bytes() == content for path, content in preserved.items())


@pytest.mark.parametrize(
    "problem", ["unknown", "malformed", "path", "missing-original", "missing-modified"]
)
def test_comparison_invalid_or_missing_inputs(comparison_inputs, tmp_path, problem):
    original, modified, _, store, comparison_id = comparison_inputs
    selection = comparison_id
    expected = b"No such file"
    if problem == "unknown":
        selection, expected = "cmp_" + "0" * 32, b"Unknown comparison ID"
    elif problem == "malformed":
        selection, expected = "ingest-run-123", b"Not a comparison ID"
    elif problem == "path":
        selection, expected = str(store / f"{comparison_id}.json"), b"Not a comparison ID"
    else:
        (original if problem == "missing-original" else modified).unlink()
    output = tmp_path / "must-not-exist.docx"
    result = _comparison_cli(
        "export-docx",
        "--blackline",
        selection,
        "--comparison-store",
        str(store),
        "--output",
        str(output),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert expected in result.stderr
    assert result.stdout == b""
    assert not output.exists()


@pytest.mark.parametrize("problem", ["schema", "id", "hash", "relative-path", "json", "list"])
def test_comparison_rejects_invalid_record(comparison_inputs, tmp_path, problem):
    _, _, _, store, comparison_id = comparison_inputs
    path = store / f"{comparison_id}.json"
    record = json.loads(path.read_text())
    key, value = {
        "schema": ("schema_version", "docx-comparison/v99"),
        "id": ("comparison_id", "cmp_" + "f" * 32),
        "hash": ("original_sha256", None),
        "relative-path": ("modified_path", "relative.docx"),
        "json": ("unused", None),
        "list": ("unused", None),
    }[problem]
    record[key] = value
    path.write_text("{" if problem == "json" else "[]" if problem == "list" else json.dumps(record))
    output = tmp_path / "no-output.docx"
    result = _comparison_cli(
        "export-docx",
        "--blackline",
        comparison_id,
        "--comparison-store",
        str(store),
        "--output",
        str(output),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert b"Invalid comparison record" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("target", ["original", "modified", "record", "record-hardlink"])
def test_comparison_preserves_sources_and_record(comparison_inputs, tmp_path, target):
    original, modified, manifest, store, comparison_id = comparison_inputs
    record_path = store / f"{comparison_id}.json"
    preserved = {path: path.read_bytes() for path in (original, modified, manifest, record_path)}
    output = {"original": original, "modified": modified}.get(target, record_path)
    if target == "record-hardlink":
        output = tmp_path / "record-alias"
        os.link(record_path, output)
    result = _comparison_cli(
        "export-docx",
        "--blackline",
        comparison_id,
        "--comparison-store",
        str(store),
        "--output",
        str(output),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert b"--output must not be the same file" in result.stderr
    assert all(path.read_bytes() == content for path, content in preserved.items())


@pytest.mark.parametrize("problem", ["missing", "not-docx"])
def test_comparison_create_rejects_unusable_input(tmp_path, problem):
    source = tmp_path / "input.docx"
    if problem == "not-docx":
        source.write_bytes(b"not a DOCX")
    store = tmp_path / "records"
    result = _comparison_cli(
        "create-comparison",
        "--original",
        str(source),
        "--modified",
        str(source),
        "--comparison-store",
        str(store),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert result.stdout == b""
    assert not store.exists()


def test_comparison_id_cannot_override_sources(comparison_inputs, tmp_path):
    original, _, _, store, comparison_id = comparison_inputs
    result = _comparison_cli(
        "export-docx",
        "--blackline",
        comparison_id,
        "--original",
        str(original),
        "--comparison-store",
        str(store),
        cwd=tmp_path,
    )
    assert result.returncode != 0
    assert b"cannot be combined" in result.stderr
    assert result.stdout == b""


def test_comparison_boolean_requires_file_pair(tmp_path):
    result = _comparison_cli("export-docx", "--blackline", cwd=tmp_path)
    assert result.returncode != 0
    assert b"requires --original and --modified" in result.stderr


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


@pytest.mark.parametrize("input_name", ["original", "modified"])
@pytest.mark.parametrize(
    "alias", ["direct", "relative", "relative-input", "normalized", "symlink", "hardlink"]
)
def test_export_rejects_input_alias_without_changing_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    input_name: str,
    alias: str,
) -> None:
    original = tmp_path / "original.docx"
    modified = tmp_path / "modified.docx"
    original.write_bytes(b"original package")
    modified.write_bytes(b"modified package")
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (original, modified)]
    original_arg, modified_arg = original, modified
    source = original if input_name == "original" else modified
    output = source
    if alias == "relative":
        monkeypatch.chdir(tmp_path)
        output = Path(source.name)
    elif alias == "relative-input":
        monkeypatch.chdir(tmp_path)
        original_arg, modified_arg = Path(original.name), Path(modified.name)
    elif alias == "normalized":
        nested = tmp_path / "nested"
        nested.mkdir()
        output = nested / ".." / source.name
    elif alias == "symlink":
        output = tmp_path / "alias.docx"
        try:
            output.symlink_to(source)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"filesystem does not support symbolic links: {exc}")
    elif alias == "hardlink":
        output = tmp_path / "alias.docx"
        if not hasattr(os, "link"):
            pytest.skip("os.link is unavailable")
        try:
            os.link(source, output)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"filesystem does not support hard links: {exc}")
    export = Mock(return_value=b"redline output must not replace an input")
    monkeypatch.setattr("doc_lineage.cli.export_docx_redline", export)

    code = main(
        [
            "export-docx",
            "--original",
            str(original_arg),
            "--modified",
            str(modified_arg),
            "--blackline",
            "--output",
            str(output),
        ]
    )

    assert [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in (original, modified)
    ] == before
    assert code == 1
    captured = capsys.readouterr()
    assert captured.err == (
        "doc-lineage export-docx: --output must not be the same file as --original or --modified\n"
    )
    assert captured.out == ""
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


def test_harvest_edgar_cli_reports_truncated_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A truncated SEC response uses the CLI error path and publishes no manifest."""
    from doc_lineage.harvest import edgar_ex10

    fixture = Path(__file__).resolve().parent / "fixtures" / "harvest" / "edgar_ex10_filing.json"
    filing = json.loads(fixture.read_text(encoding="utf-8"))
    monkeypatch.setattr(edgar_ex10, "_load_filing_from_edgar", lambda cik: filing)
    monkeypatch.setattr(edgar_ex10, "_rate_limit", lambda: None)
    response = MagicMock()
    response.__enter__.return_value.read.side_effect = http.client.IncompleteRead(b"partial", 20)
    monkeypatch.setattr(edgar_ex10.urllib.request, "urlopen", Mock(return_value=response))
    output = tmp_path / "out"

    assert main(["harvest-edgar", "--cik", "0001067983", "--output", str(output)]) == 1

    captured = capsys.readouterr()
    assert "network error fetching" in captured.err
    assert "IncompleteRead" in captured.err
    assert "Traceback" not in captured.err
    assert not (output / "artifact-manifest.json").exists()
