"""Actual PDFs and independent CLI processes; no substituted ingest/parser output."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from reportlab.pdfgen import canvas

from doc_lineage.blackline import (
    align_sections,
    build_section_tree,
    create_section_comparison,
    lineage_edge_for,
    load_section_comparison,
)
from doc_lineage.ingest import Segment

ROOT = Path(__file__).resolve().parents[2]


def cli(*args: object, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "doc_lineage.cli", *map(str, args)],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def make_runs(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    for name, fee, headings in [
        ("before", "two", ["1. FEES", "2. TERM", "2. TERM", "3. NOTICE"]),
        ("after", "three", ["1. FEES", "2. TERM", "4. TAXES"]),
    ]:
        source = root / f"{name}.pdf"
        pdf = canvas.Canvas(str(source), invariant=1)
        # One section per page gives real backend-independent segment boundaries.
        for header in headings:
            pdf.drawString(72, 720, header)
            pdf.drawString(72, 700, f"The fee is {fee} percent.")
            pdf.showPage()
        pdf.save()
        before = source.read_bytes()
        result = cli(
            "ingest", source, "--output", root / name, "--no-docling", "--no-ocr", cwd=root
        )
        assert result.returncode == 0, result.stderr
        assert source.read_bytes() == before, "INGEST_PRESERVES_ORIGINAL"
        manifest = json.loads((root / name / "artifact-manifest.json").read_bytes())
        snapshot = root / name / f"source-{manifest['source']['sha256']}.bin"
        assert snapshot.read_bytes() == before
        source.unlink()  # Comparison has only persisted run directories.
    return root / "before", root / "after"


@pytest.fixture
def runs(tmp_path: Path) -> tuple[Path, Path]:
    return make_runs(tmp_path)


def test_independent_ingest_compare_lookup_replay(runs: tuple[Path, Path], tmp_path: Path) -> None:
    left, right = runs
    store = tmp_path / "store"
    result = cli("pair-sections", left, right, "--store", store, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    cid = result.stdout.strip()
    assert re.fullmatch(r"cmp_[0-9a-f]{32}", cid)
    artifact = store / f"{cid}.json"
    raw = artifact.read_bytes()
    record = json.loads(raw)
    trees = []
    for role, run in [("original", left), ("modified", right)]:
        payload_bytes = (run / "segments.json").read_bytes()
        manifest_bytes = (run / "artifact-manifest.json").read_bytes()
        payload = json.loads(payload_bytes)
        manifest = json.loads(manifest_bytes)
        binding = record["identity"][role]
        assert binding == {
            "source_sha256": manifest["source"]["sha256"],
            "segments_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        }
        trees.append(
            build_section_tree(
                [Segment(**s) for s in payload["segments"]], source_sha256=binding["source_sha256"]
            )
        )
    assert (
        record["identity"]["original"]["source_sha256"]
        != record["identity"]["modified"]["source_sha256"]
    )
    expected = [lineage_edge_for(p) for p in align_sections(*trees)]
    assert record["decisions"] == expected, "PERSISTED_SECTION_DECISIONS_MATCH_ENGINE"
    assert [d["pairing_method"] for d in expected] == [
        "section_id",
        "manual_review",
        "manual_review",
        "manual_review",
        "manual_review",
    ]
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    replay = cli("lookup-section-pairing", cid, "--store", store, cwd=elsewhere)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout) == record
    assert artifact.read_bytes() == raw, "LOOKUP_MUST_NOT_REWRITE"
    relocated = tmp_path / "moved"
    relocated.mkdir()
    for directory in [left, right, store]:
        shutil.move(str(directory), relocated / directory.name)
    assert load_section_comparison(cid, store=relocated / "store") == record


@pytest.mark.parametrize(
    "failure",
    [
        "unknown",
        "path",
        "order",
        "options",
        "missing",
        "segment",
        "source",
        "manifest",
        "record",
        "decisions",
    ],
)
def test_lookup_fails_before_output(runs: tuple[Path, Path], tmp_path: Path, failure: str) -> None:
    left, right = runs
    store = tmp_path / "store"
    cid = create_section_comparison(left, right, store=store)
    artifact = store / f"{cid}.json"
    selection = cid
    extra: list[object] = []
    expected = ""
    if failure == "unknown":
        selection, expected = "cmp_" + "f" * 32, "unknown comparison ID"
    elif failure == "path":
        selection, expected = str(artifact), "not a comparison ID"
    elif failure == "order":
        extra, expected = ["--original-run", right, "--modified-run", left], "source order mismatch"
    elif failure == "options":
        extra, expected = ["--threshold", "0.5"], "pairing options mismatch"
    elif failure == "missing":
        (left / "segments.json").unlink()
        expected = "missing or unreadable ingest artifact"
    elif failure == "segment":
        with (left / "segments.json").open("ab") as out:
            out.write(b" ")
        expected = "hash/size mismatch"
    elif failure == "source":
        source = next(left.glob("source-*.bin"))
        source.write_bytes(source.read_bytes() + b"\n")
        expected = "hash/size mismatch"
    elif failure == "manifest":
        with (left / "artifact-manifest.json").open("ab") as out:
            out.write(b" ")
        expected = "input tamper"
    else:
        record = json.loads(artifact.read_bytes())
        if failure == "record":
            record["identity"]["mode"] = "native-docx"
        else:
            record["decisions"] = []
        artifact.write_text(json.dumps(record))
        expected = "artifact tamper"
    snapshot = {p.name: p.read_bytes() for p in store.iterdir()}
    result = cli("lookup-section-pairing", selection, "--store", store, *extra, cwd=tmp_path)
    assert result.returncode == 1, result.stdout
    assert result.stdout == ""
    assert expected in result.stderr
    assert "Traceback" not in result.stderr
    assert {p.name: p.read_bytes() for p in store.iterdir()} == snapshot


@pytest.mark.parametrize(
    "failure",
    [
        "segments",
        "manifest",
        "original",
        "legacy",
        "unsafe",
        "symlink",
        "duplicate",
        "schema",
        "binding",
        "row",
        "options",
    ],
)
def test_creation_rejects_invalid_ingest_without_publication(
    runs: tuple[Path, Path], tmp_path: Path, failure: str
) -> None:
    left, right = runs
    manifest_path = left / "artifact-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if failure in {"segments", "manifest", "original"}:
        path = {
            "segments": left / "segments.json",
            "manifest": manifest_path,
            "original": next(left.glob("source-*.bin")),
        }[failure]
        path.unlink()
    elif failure == "legacy":
        manifest["artifacts"] = [
            a for a in manifest["artifacts"] if not a["path"].startswith("source-")
        ]
    elif failure == "unsafe":
        manifest["artifacts"][0]["path"] = "../source.bin"
    elif failure == "symlink":
        path = left / "segments.json"
        backup = left / "backup.json"
        path.rename(backup)
        path.symlink_to(backup)
    elif failure == "duplicate":
        manifest["artifacts"].append(manifest["artifacts"][0])
    elif failure == "schema":
        manifest["tool"] = "other"
    elif failure == "binding":
        manifest["source"]["sha256"] = "0" * 64
    elif failure == "row":
        path = left / "segments.json"
        payload = json.loads(path.read_bytes())
        payload["segments"][0]["order"] = 99
        path.write_text(json.dumps(payload))
        for a in manifest["artifacts"]:
            if a["path"] == "segments.json":
                a.update(
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size
                )
    if failure not in {"segments", "manifest", "original"}:
        manifest_path.write_text(json.dumps(manifest))
    store = tmp_path / "never-published"
    args: list[object] = ["--threshold", "nan"] if failure == "options" else []
    result = cli("pair-sections", left, right, "--store", store, *args, cwd=tmp_path)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert not store.exists(), "INVALID_INPUT_MUST_NOT_PUBLISH"


def test_options_and_order_bind_new_comparison_identity(
    runs: tuple[Path, Path], tmp_path: Path
) -> None:
    left, right = runs
    store = tmp_path / "store"
    records: list[dict[str, Any]] = []
    for a, b, threshold in [(left, right, 0.8), (right, left, 0.8), (left, right, 0.5)]:
        cid = create_section_comparison(a, b, store=store, threshold=threshold)
        records.append(load_section_comparison(cid, store=store))
    assert len({r["comparison_id"] for r in records}) == 3
    assert len({r["identity_sha256"] for r in records}) == 3
