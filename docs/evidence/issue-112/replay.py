"""Portable real-PDF subprocess proof; invoke with the repository Python runtime."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONPATH": str(repo / "src")}
    commands = []

    def run(*arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        argv = [sys.executable, "-m", "doc_lineage.cli", *arguments]
        result = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True)
        commands.append(
            {
                "argv": argv,
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        assert result.returncode == expected, result.stdout + result.stderr
        if expected:
            assert result.stdout == ""
        return result

    sources = {}
    for name in ["before", "after"]:
        source = here / "fixtures" / f"{name}.pdf"
        sources[name] = hashlib.sha256(source.read_bytes()).hexdigest()
        shutil.copyfile(source, work / f"{name}.pdf")
        run("ingest", f"{name}.pdf", "--output", name, "--no-docling", "--no-ocr")
        assert hashlib.sha256((work / f"{name}.pdf").read_bytes()).hexdigest() == sources[name]
        (work / f"{name}.pdf").unlink()
    assert sources["before"] != sources["after"]
    cid = run("pair-sections", "before", "after", "--store", "store").stdout.strip()
    artifact = work / "store" / f"{cid}.json"
    raw = artifact.read_bytes()
    record = json.loads(raw)
    result = run("lookup-section-pairing", cid, "--store", "store")
    assert json.loads(result.stdout) == record
    assert artifact.read_bytes() == raw
    assert record["identity"]["original"]["source_sha256"] == sources["before"]
    assert record["identity"]["modified"]["source_sha256"] == sources["after"]
    assert [d["section_id"] for d in record["decisions"]] == ["1", "2", "2", "3", "4"]
    for name in ["before", "after"]:
        role = "original" if name == "before" else "modified"
        for file, field in [
            ("segments.json", "segments_sha256"),
            ("artifact-manifest.json", "manifest_sha256"),
        ]:
            assert (
                hashlib.sha256((work / name / file).read_bytes()).hexdigest()
                == record["identity"][role][field]
            )
    result = run(
        "lookup-section-pairing",
        cid,
        "--store",
        "store",
        "--original-run",
        "after",
        "--modified-run",
        "before",
        expected=1,
    )
    assert "source order mismatch" in result.stderr
    result = run(
        "lookup-section-pairing", cid, "--store", "store", "--threshold", "0.5", expected=1
    )
    assert "pairing options mismatch" in result.stderr
    result = run("lookup-section-pairing", "cmp_" + "f" * 32, "--store", "store", expected=1)
    assert "unknown comparison ID" in result.stderr
    result = run("lookup-section-pairing", f"store/{cid}.json", "--store", "store", expected=1)
    assert "not a comparison ID" in result.stderr
    path = work / "before" / "segments.json"
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    result = run("pair-sections", "before", "after", "--store", "never-published", expected=1)
    assert "hash/size mismatch" in result.stderr
    assert not (work / "never-published").exists()
    path.write_bytes(original)
    assert artifact.read_bytes() == raw
    (work / "argv-results.json").write_text(json.dumps(commands, indent=2) + "\n")
    (work / "source-hashes.json").write_text(json.dumps(sources, indent=2) + "\n")
    print("PASS: independent ingest, comparison, ID-only lookup and explicit failure receipts")


if __name__ == "__main__":
    main()
