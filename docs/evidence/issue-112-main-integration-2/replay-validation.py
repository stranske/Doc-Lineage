from validate import OUT, PY, run

assert run("combined-replay", [PY, str(OUT / "combined-replay.py"), str(OUT / "combined-run")]) == 0
assert (
    run("real-pdf-replay", [PY, "docs/evidence/issue-112/replay.py", str(OUT / "real-pdf-replay")])
    == 0
)
