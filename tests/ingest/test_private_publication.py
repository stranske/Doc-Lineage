"""Real filesystem regressions for private ingest and durable publication."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from doc_lineage import blackline, persistence
from doc_lineage.cli import main
from doc_lineage.ingest import ingest_document

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_lpa.pdf"


@pytest.mark.parametrize("reuse", [False, True, "changed"])
def test_ingest_artifacts_owner_only_under_permissive_umask(
    tmp_path: Path, reuse: bool | str
) -> None:
    run = tmp_path / "run"
    if reuse:
        previous_source = FIXTURE
        if reuse == "changed":
            previous_source = tmp_path / "previous.pdf"
            previous_source.write_bytes(
                FIXTURE.read_bytes().replace(b"MANAGEMENT FEE", b"DIFFERENT FEE!")
            )
        ingest_document(previous_source, output_dir=run, allow_docling=False)
        for path in [run, *run.rglob("*")]:
            path.chmod(0o777 if path.is_dir() else 0o666)
    previous = os.umask(0)
    try:
        result = ingest_document(FIXTURE, output_dir=run, allow_docling=False)
        assert stat.S_IMODE(run.stat().st_mode) == 0o700, "INGEST_RUN_IS_PRIVATE"
        for path in run.rglob("*"):
            expected = 0o700 if path.is_dir() else 0o600
            assert stat.S_IMODE(path.stat().st_mode) == expected, "INGEST_ARTIFACT_IS_PRIVATE"
        for artifact in result.manifest["artifacts"]:
            assert (run / artifact["path"]).is_file()
        assert (run / f"source-{result.source_sha256}.bin").read_bytes() == FIXTURE.read_bytes()
    finally:
        os.umask(previous)


@pytest.mark.parametrize("failure", ["write", "file-sync", "link", "directory-sync"])
def test_snapshot_failure_cleanup_and_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    run = tmp_path / "run"
    fdopen, fsync, link = os.fdopen, os.fsync, os.link

    class InterruptedWriter:
        def __init__(self, handle: Any) -> None:
            self.handle = handle

        def __enter__(self) -> InterruptedWriter:
            self.handle.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self.handle.__exit__(*args)

        def fileno(self) -> int:
            return self.handle.fileno()

        def write(self, payload: bytes) -> None:
            self.handle.write(payload[: len(payload) // 2])
            self.handle.flush()
            raise KeyboardInterrupt("interrupted snapshot write")

    def interrupted(fd: int, mode: str) -> InterruptedWriter:
        return InterruptedWriter(fdopen(fd, mode))

    def failed_sync(fd: int) -> None:
        directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        if directory == (failure == "directory-sync"):
            raise OSError("injected sync failure")
        fsync(fd)

    def failed_link(*args: Any, **kwargs: Any) -> None:
        raise OSError("injected publication failure")

    with monkeypatch.context() as patch:
        if failure == "write":
            patch.setattr(persistence.os, "fdopen", interrupted)
        elif failure == "link":
            patch.setattr(persistence.os, "link", failed_link)
        else:
            patch.setattr(persistence.os, "fsync", failed_sync)
        with pytest.raises((KeyboardInterrupt, OSError)):
            ingest_document(FIXTURE, output_dir=run, allow_docling=False)
    assert not list(run.glob(".snapshot-*")), "SNAPSHOT_FAILURE_CLEANS_TEMPORARY"
    finals = list(run.glob("source-*.bin"))
    if failure == "directory-sync":
        assert len(finals) == 1 and finals[0].read_bytes() == FIXTURE.read_bytes()
    else:
        assert not finals, "INTERRUPTED_SNAPSHOT_NEVER_PUBLISHES_FINAL"
    assert not (run / "artifact-manifest.json").exists()
    ingest_document(FIXTURE, output_dir=run, allow_docling=False)
    assert next(run.glob("source-*.bin")).read_bytes() == FIXTURE.read_bytes()
    assert not list(run.glob(".snapshot-*"))
    assert link is os.link  # Fault injection did not leak into retry.


def test_snapshot_atomic_no_overwrite_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = tmp_path / "run"
    link = os.link
    winner = b"concurrent winner bytes"

    def racing_link(source: Any, target: Any) -> None:
        Path(target).write_bytes(winner)
        link(source, target)  # The actual exclusive publication must fail.

    with monkeypatch.context() as patch:
        patch.setattr(persistence.os, "link", racing_link)
        with pytest.raises(FileExistsError):
            ingest_document(FIXTURE, output_dir=run, allow_docling=False)
    snapshot = next(run.glob("source-*.bin"))
    assert snapshot.read_bytes() == winner, "SNAPSHOT_PUBLICATION_NEVER_OVERWRITES"
    assert not list(run.glob(".snapshot-*"))
    with pytest.raises(ValueError, match="immutable"):
        ingest_document(FIXTURE, output_dir=run, allow_docling=False)
    assert snapshot.read_bytes() == winner


def make_runs(tmp_path: Path) -> tuple[Path, Path]:
    left, right = tmp_path / "before", tmp_path / "after"
    changed = tmp_path / "changed.pdf"
    changed.write_bytes(FIXTURE.read_bytes().replace(b"MANAGEMENT FEE", b"DIFFERENT FEE!"))
    ingest_document(FIXTURE, output_dir=left, allow_docling=False)
    ingest_document(changed, output_dir=right, allow_docling=False)
    return left, right


def test_comparison_durable_publication_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    left, right = make_runs(tmp_path)
    store = tmp_path / "store"
    events: list[str] = []
    fsync, link, unlink = os.fsync, os.link, Path.unlink

    def observe_sync(fd: int) -> None:
        events.append("directory-sync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file-sync")
        fsync(fd)

    def observe_link(source: Any, target: Any) -> None:
        assert Path(source).read_bytes()
        assert not Path(target).exists()
        events.append("publish")
        link(source, target)

    def observe_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.parent == store:
            events.append("cleanup")
        unlink(path, *args, **kwargs)

    monkeypatch.setattr(persistence.os, "fsync", observe_sync)
    monkeypatch.setattr(persistence.os, "link", observe_link)
    monkeypatch.setattr(Path, "unlink", observe_unlink)
    cid = blackline.create_section_comparison(left, right, store=store)
    assert events == [
        "file-sync",
        "publish",
        "cleanup",
        "directory-sync",
    ], "DURABLE_COMPARISON_ORDER"
    assert blackline.load_section_comparison(cid, store=store)["comparison_id"] == cid
    assert not list(store.glob(".section-*"))


@pytest.mark.parametrize("failure", ["file-sync", "link", "directory-sync"])
def test_comparison_publication_failure_never_returns_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    left, right = make_runs(tmp_path)
    store = tmp_path / "store"
    fsync = os.fsync

    def failed_sync(fd: int) -> None:
        directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        if directory == (failure == "directory-sync"):
            raise OSError("publication sync failed")
        fsync(fd)

    def failed_link(*args: Any, **kwargs: Any) -> None:
        raise OSError("publication link failed")

    with monkeypatch.context() as patch:
        patch.setattr(
            persistence.os,
            "link" if failure == "link" else "fsync",
            failed_link if failure == "link" else failed_sync,
        )
        assert main(["pair-sections", str(left), str(right), "--store", str(store)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "", "FAILED_PUBLICATION_RETURNS_NO_COMPARISON_ID"
    assert "failed" in captured.err
    assert not list(store.glob(".section-*"))
    records = list(store.glob("cmp_*.json"))
    assert len(records) == (1 if failure == "directory-sync" else 0)
    previous = {p: p.read_bytes() for p in records}
    cid = blackline.create_section_comparison(left, right, store=store)
    assert blackline.load_section_comparison(cid, store=store)
    assert all(p.read_bytes() == payload for p, payload in previous.items())


def test_comparison_collision_preserves_winner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    left, right = make_runs(tmp_path)
    store = tmp_path / "store"
    monkeypatch.setattr(blackline, "uuid4", lambda: UUID(int=1))
    cid = blackline.create_section_comparison(left, right, store=store)
    path = store / f"{cid}.json"
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        blackline.create_section_comparison(right, left, store=store)
    assert path.read_bytes() == before, "COMPARISON_PUBLICATION_NEVER_OVERWRITES"
    assert not list(store.glob(".section-*"))


def test_snapshot_durable_publication_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = tmp_path / "run"
    events: list[str] = []
    fsync, link, unlink = os.fsync, os.link, Path.unlink

    def observe_sync(fd: int) -> None:
        events.append("directory-sync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file-sync")
        fsync(fd)

    def observe_link(source: Any, target: Any) -> None:
        assert Path(source).read_bytes() == FIXTURE.read_bytes()
        assert stat.S_IMODE(Path(source).stat().st_mode) == 0o600
        assert not Path(target).exists()
        events.append("publish")
        link(source, target)

    def observe_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.name.startswith(".snapshot-"):
            events.append("cleanup")
        unlink(path, *args, **kwargs)

    monkeypatch.setattr(persistence.os, "fsync", observe_sync)
    monkeypatch.setattr(persistence.os, "link", observe_link)
    monkeypatch.setattr(Path, "unlink", observe_unlink)
    ingest_document(FIXTURE, output_dir=run, allow_docling=False)
    assert events == [
        "file-sync",
        "publish",
        "cleanup",
        "directory-sync",
        "directory-sync",
    ], "DURABLE_SNAPSHOT_ORDER"
