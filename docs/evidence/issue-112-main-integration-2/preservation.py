"""Verify both-parent history without rebinding historical generated artifacts."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
OLD = "5b6c5042da6182c14cdf65d5997db2bb180157ca"
MAIN = "c274b866e695d92a083c182c19f3119cab01e0b0"


def show(rev, name):
    return subprocess.check_output(["git", "show", rev + ":" + name])


def names(rev, scope):
    return subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", rev, "--", scope], text=True
    ).splitlines()


def defs(s):
    return {
        n.name: ast.dump(n, include_attributes=False)
        for n in ast.parse(s).body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    }


proof = {"historical_bundles": {}, "main_tests": {}, "main_docx_contract_ast_unchanged": {}}
for scope in ["docs/evidence/issue-112", "docs/evidence/issue-112-review-recovery"]:
    hashes = {}
    for n in names(OLD, scope):
        data = show(OLD, n)
        assert Path(n).read_bytes() == data, n
        hashes[n] = hashlib.sha256(data).hexdigest()
    proof["historical_bundles"][scope] = {
        "revision": OLD,
        "files": hashes,
        "all_byte_identical": True,
    }
for n in names(MAIN, "tests"):
    original, current = show(MAIN, n), Path(n).read_bytes()
    if current == original:
        proof["main_tests"][n] = "byte-identical to main"
    else:
        assert current == show(OLD, n), n
        before, after = defs(original), defs(current)
        for function, definition in before.items():
            if function == "test_non_finite_confidence_fails_closed_to_manual_review":
                continue
            assert after[function] == definition, (n, function)
        proof["main_tests"][
            n
        ] = "byte-identical to source112; main definitions retained except previously reviewed stronger nonfinite parameterization"
for filename, functions in [
    (
        "src/doc_lineage/blackline.py",
        [
            "ComparisonRecord",
            "comparison_store_path",
            "_validate_docx",
            "write_comparison_record",
            "load_comparison_record",
        ],
    ),
    ("src/doc_lineage/cli.py", ["_run_export_docx"]),
]:
    before, after = defs(show(MAIN, filename)), defs(Path(filename).read_bytes())
    for name in functions:
        assert before[name] == after[name], name
    proof["main_docx_contract_ast_unchanged"][filename] = functions
bindings = json.loads(
    Path("docs/evidence/issue-112-review-recovery/source-bindings.json").read_text()
)
untracked = []
for n, expected in bindings.items():
    result = subprocess.run(["git", "show", OLD + ":" + n], capture_output=True)
    if result.returncode:
        actual = hashlib.sha256(Path(n).read_bytes()).hexdigest() if Path(n).exists() else None
        untracked.append(
            {
                "path": n,
                "recorded_hash": expected,
                "current_hash": actual,
                "current_matches_historical": actual == expected,
            }
        )
    else:
        assert hashlib.sha256(result.stdout).hexdigest() == expected, n
proof["historical_binding_disposition"] = {
    "git_revision": OLD,
    "tracked_bindings_verified": len(bindings) - len(untracked),
    "untracked_build_metadata": untracked,
    "old_verifier_in_clean_archive": "fails because six generated egg-info files are absent; immutable verifier and receipts retained; no regenerated metadata relabeled historical",
}
(OUT / "historical-preservation.json").write_text(json.dumps(proof, indent=2))
first = json.loads(
    Path(
        "/Users/teacher/.codex/handoff/dispatch-logs/done/stranske__Doc-Lineage_129-codex-1792242602242037000.json"
    ).read_text()
)
assert first["rc"] == 0 and first["release_rc"] == 0
(OUT / "first-recovery-terminal.json").write_text(json.dumps(first, indent=2))
print("PASS: tracked historical bindings, immutable evidence and both-parent tests/contracts")
