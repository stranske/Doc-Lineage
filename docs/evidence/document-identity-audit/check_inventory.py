"""Check that the dated audit inventories every exact required rg match once."""

import re
import subprocess
from pathlib import Path

QUERY = 'locator|"page"|document_ref|supersedes|supersession_evidence'
REPORT = Path("docs/reports/document-identity-conformance-audit.md")


def check(report):
    output = subprocess.run(
        ["rg", "-n", QUERY, "src/doc_lineage"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    expected = {tuple(line.split(":", 2)[:2]) for line in output.splitlines()}
    rows = re.findall(r"^\| `([^`]+):(\d+)` \|", report, re.MULTILINE)
    assert len(rows) == len(set(rows)), "duplicate required inventory row"
    assert set(rows) == expected, f"missing={expected - set(rows)} extra={set(rows) - expected}"
    print(f"PASS: {len(expected)} exact source matches inventoried once")


if __name__ == "__main__":
    check(REPORT.read_text())
