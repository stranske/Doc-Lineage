"""Verify original evidence at its real revision and separately admit current inputs."""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HISTORY = "8840dbbf3f5bc864bd1e25511a771c59d804517b"
PREFIX = "docs/evidence/issue-112-main-integration-2"
HELPER_SHA = "12b0955111e348543e55ac9fbc06599b3e79294781198c6fb1b46f3029867c36"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def junit(
    name: str,
    total: int,
    failures: int,
    expected_node: str | None = None,
    marker: str | None = None,
) -> set[tuple[str, str]]:
    root = ET.parse(HERE / name).getroot()
    require(
        root.tag == "testsuites" and all(child.tag == "testsuite" for child in root),
        f"JUnit root structure: {name}",
    )
    suites = list(root)
    require(bool(suites), f"missing suite: {name}")
    require(
        all(
            all(c.tag in {"testcase", "properties", "system-out", "system-err"} for c in suite)
            for suite in suites
        ),
        f"detached failure or unexpected suite child: {name}",
    )
    cases = [case for suite in suites for case in suite.findall("testcase")]
    identities = [(case.attrib.get("classname", ""), case.attrib.get("name", "")) for case in cases]
    require(all(all(identity) for identity in identities), f"missing testcase identity: {name}")
    require(
        len(identities) == len(set(identities)) == total,
        f"duplicate or wrong testcase identity count: {name}",
    )
    require(
        not list(root.iter("error")) and not list(root.iter("skipped")), f"errors/skips: {name}"
    )
    attached = [failure for case in cases for failure in case.findall("failure")]
    require(
        len(attached) == len(list(root.iter("failure"))) == failures,
        f"detached/wrong failures: {name}",
    )
    for suite in suites:
        own = suite.findall("testcase")
        require(int(suite.attrib["tests"]) == len(own), f"declared tests: {name}")
        require(
            int(suite.attrib["failures"]) == sum(len(c.findall("failure")) for c in own),
            f"declared failures: {name}",
        )
        require(
            int(suite.attrib["errors"]) == int(suite.attrib["skipped"]) == 0,
            f"declared errors/skips: {name}",
        )
    if expected_node is not None:
        module, test = expected_node.split("::", 1)
        identity = (module.removesuffix(".py").replace("/", "."), test)
        require(identities == [identity], f"wrong control testcase: {name}")
    if failures:
        require(
            total == failures == 1 and marker is not None,
            f"invalid control failure topology: {name}",
        )
        failure = attached[0]
        require(
            (
                failure.attrib.get("type", "").endswith("AssertionError")
                or (
                    "type" not in failure.attrib
                    and failure.attrib.get("message", "").startswith("AssertionError:")
                )
            ),
            f"non-assertion RED: {name}",
        )
        require(marker in (failure.text or ""), f"wrong assertion: {name}")
    return set(identities)


def controls():
    # Only the eight fixed variant declarations at the real original Git revision.
    tree = ast.parse(git("show", HISTORY + ":" + PREFIX + "/causal.py"))
    declarations = [
        n
        for n in tree.body
        if (
            isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "variants" for t in n.targets)
        )
        or (
            isinstance(n, ast.AugAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "variants"
        )
    ]
    namespace = {}
    exec(
        compile(
            ast.Module(body=declarations, type_ignores=[]), "immutable-control-declarations", "exec"
        ),
        namespace,
    )
    result = {}
    for name, path, mutate, node, marker in namespace["variants"]:
        if "::" not in node:
            node = "tests/ingest/test_private_publication.py::" + node
        if name == "pdf-engine-wiring":
            marker = "PERSISTED_SECTION_PAIRING_MUST_CALL_EXISTING_ENGINE"
        result[name] = (path, mutate, node, marker)
    require(len(result) == 8, "immutable controls incomplete")
    return result


def check_receipt(name: str, tests: int, failures: int, node: str | None = None) -> None:
    row = json.loads((HERE / (name + ".json")).read_text())
    require(
        (row["tests"], row["failures"], row["errors"], row["skipped"], row["returncode"])
        == (tests, failures, 0, 0, int(failures > 0)),
        f"receipt/XML disagreement: {name}",
    )
    argv = row["argv"]
    require(
        argv[1:3] == ["-m", "pytest"] and Path(argv[0]).name == "python",
        f"wrong capture command: {name}",
    )
    require(Path(row["cwd"]).is_absolute(), f"missing capture cwd: {name}")
    require(
        sum(a.startswith("--junitxml=") for a in argv) == 1
        and any(a.endswith("/" + name + ".xml") for a in argv if a.startswith("--junitxml=")),
        f"wrong XML output command: {name}",
    )
    require(
        argv[3] == node if node is not None else argv[3] == "-q", f"wrong test selection: {name}"
    )
    require(
        not any(a == "-k" or a.startswith("--ignore") or a == "-m" for a in argv[3:]),
        f"filtered acceptance run: {name}",
    )


def main() -> None:
    inventory = json.loads((HERE / "inventory.json").read_text())
    actual = {p.name for p in HERE.iterdir() if p.is_file()} - {
        "inventory.json",
        "verify.py",
        "README.md",
    }
    require(actual == set(inventory), "capture inventory incomplete")
    for name, expected in inventory.items():
        require(Path(name).name == name, "capture path is not a filename")
        require(digest(HERE / name) == expected, f"capture digest mismatch: {name}")
    # Run the unchanged original checker against its immutable real Git snapshot.
    # It is explicitly historical proof, never rebound to the current formatter head.
    with tempfile.TemporaryDirectory(prefix="doc129-history-") as tmp:
        historical = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(git("archive", HISTORY))) as archive:
            archive.extractall(historical, filter="data")
        checker = historical / PREFIX / "verify.py"
        namespace = {"__file__": str(checker), "__name__": "historical_checker"}
        exec(compile(checker.read_bytes(), str(checker), "exec", optimize=0), namespace)
        namespace["git_bytes"] = lambda rev, path: git("show", rev + ":" + path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            namespace["main"]()
        print("HISTORICAL_ARCHIVE_PASS:", HISTORY, output.getvalue().strip())
    bindings = json.loads((HERE / "source-bindings.json").read_text())
    revision = bindings["revision"]
    expected_paths = set(
        git(
            "ls-tree",
            "-r",
            "--name-only",
            revision,
            "src",
            "tests",
            "schemas",
            "vocab",
            "docs/contracts/schemas",
            "pyproject.toml",
        )
        .decode()
        .splitlines()
    )
    require(expected_paths == set(bindings["tracked"]), "current input inventory incomplete")
    for name, expected in bindings["tracked"].items():
        require(digest(ROOT / name) == expected, f"CURRENT_INPUT_DRIFT: {name}")
        require(
            hashlib.sha256(git("show", revision + ":" + name)).hexdigest() == expected,
            f"immutable input mismatch: {name}",
        )
    full = json.loads((HERE / "full.json").read_text())
    require(full["returncode"] == 0 and full["tests"] == 671, "full suite did not pass")
    full_identities = junit("full.xml", 671, 0)
    check_receipt("full", 671, 0)
    coverage = ET.parse(HERE / "coverage.xml").getroot()
    lv, lc, bv, bc = (
        int(coverage.attrib[k])
        for k in ("lines-valid", "lines-covered", "branches-valid", "branches-covered")
    )
    require(lv > 0 and bv > 0 and 0 <= lc <= lv and 0 <= bc <= bv, "invalid coverage counts")
    require(
        abs(float(coverage.attrib["line-rate"]) - lc / lv) <= 0.0001
        and abs(float(coverage.attrib["branch-rate"]) - bc / bv) <= 0.0001,
        "coverage count/rate mismatch",
    )
    require((lc + bc) / (lv + bv) >= 0.80, "normal combined line/branch floor not met")
    specs = controls()
    proofs = json.loads((HERE / "causal-proof.json").read_text())
    names = {
        "privacy-directory",
        "privacy-artifact",
        "snapshot-publication",
        "directory-durability",
        "docx-cli-dispatch",
        "pdf-cli-dispatch",
        "pdf-engine-wiring",
        "docx-source-hash-wiring",
    }
    require(len(proofs) == 8 and {p["variant"] for p in proofs} == names, "causal controls missing")
    bound_tests = {
        path: sha for path, sha in bindings["tracked"].items() if path.startswith("tests/")
    }
    for proof in proofs:
        name = proof["variant"]
        path, mutate, node, marker = specs[name]
        require(proof["path"] == path and proof["node"] == node, f"control mapping changed: {name}")
        green = (ROOT / path).read_bytes()
        require(
            digest(ROOT / path) == proof["green_sha256"] == proof["restored_sha256"],
            f"restoration mismatch: {name}",
        )
        require(
            (HERE / (name + ".green.py.txt")).read_bytes() == green, f"wrong green source: {name}"
        )
        red = (HERE / (name + ".red.py.txt")).read_bytes()
        require(
            red != green
            and red == mutate(green.decode()).encode()
            and hashlib.sha256(red).hexdigest() == proof["red_sha256"],
            f"wrong disconnection: {name}",
        )
        require(
            proof["unchanged_test_hashes"] == bound_tests, f"incomplete/changed test hashes: {name}"
        )
        for test_path, expected in bound_tests.items():
            require(digest(ROOT / test_path) == expected, f"causal test changed: {test_path}")
        control_id = junit(name + "-red.xml", 1, 1, node, marker)
        require(control_id <= full_identities, f"full suite omitted acceptance control: {name}")
        require(
            junit(name + "-restored.xml", 1, 0, node) == control_id,
            f"different restored test: {name}",
        )
        for state, code in [("red", 1), ("restored", 0)]:
            check_receipt(name + "-" + state, 1, code, node)
        require(marker in (HERE / (name + "-red.log")).read_text(), f"wrong RED console: {name}")
    native = [json.loads(line) for line in (HERE / "native.jsonl").read_text().splitlines()]
    before_paths, after_paths, active = set(), set(), set()
    for event in native:
        phase, path = event["phase"], event["path"]
        require(phase in {"before", "after"}, "unknown native phase")
        if phase == "before":
            require(
                path not in before_paths
                and path not in active
                and event["argv"][0] == path
                and event["sha256"] == HELPER_SHA,
                "duplicate, inconsistent or unknown helper",
            )
            before_paths.add(path)
            active.add(path)
        else:
            require(
                path in active and path not in after_paths and event["returncode"] == 0,
                "unmatched, duplicate, unordered or failed native completion",
            )
            active.remove(path)
            after_paths.add(path)
    require(
        not active and before_paths == after_paths and len(before_paths) == 16,
        "native execution chain incomplete",
    )
    provenance = json.loads((HERE / "provenance.json").read_text())
    require(
        digest(HERE / "native-observer.py.txt") == provenance["native_observer_sha256"],
        "native instrumentation missing",
    )
    require(
        provenance["snapshot_publication_after_capture"] is True
        and digest(HERE / "package.py.txt") == provenance["packager_sha256"],
        "snapshot publication provenance missing",
    )
    print(
        "CURRENT_ADMISSION_PASS: exact current inputs;671 real passes;8 identity-bound assertion RED/restored GREEN controls;16 matched native executions"
    )


if __name__ == "__main__":
    main()
