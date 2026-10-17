import base64
import datetime
import json
import pathlib
import re
import subprocess
import sys

OUT = pathlib.Path("/private/tmp/dl129-second") / sys.argv[1]
OUT.mkdir(parents=True, exist_ok=False)
WRAP = "/Users/teacher/.codex/bin/detached-net.sh"


def gh(label, args):
    p = subprocess.run([WRAP, "gh", *args], cwd="/tmp", capture_output=True, text=True, timeout=90)
    (OUT / f"{label}.stderr").write_text(p.stderr)
    (OUT / f"{label}.json").write_text(p.stdout)
    if p.returncode:
        raise RuntimeError(label + " failed: " + p.stderr)
    return json.loads(p.stdout)


pr = gh(
    "pr",
    [
        "pr",
        "view",
        "129",
        "-R",
        "stranske/Doc-Lineage",
        "--json",
        "headRefOid,headRefName,isDraft,state,url",
    ],
)
if (
    pr["headRefOid"] != "5b6c5042da6182c14cdf65d5997db2bb180157ca"
    or pr["isDraft"]
    or pr["state"] != "OPEN"
):
    raise RuntimeError("exact target changed or not ready/open")
main = gh("main-ref", ["api", "repos/stranske/Doc-Lineage/git/ref/heads/main"])
assert (
    main["object"]["sha"] == "c274b866e695d92a083c182c19f3119cab01e0b0"
), "main changed beyond this bounded integration"
branch = gh(
    "branch-ref",
    [
        "api",
        "repos/stranske/Doc-Lineage/git/ref/heads/codex/issue-112-content-bound-section-pairing",
    ],
)
assert (
    branch["object"]["sha"] == "5b6c5042da6182c14cdf65d5997db2bb180157ca"
), "remote branch changed"
records = []
for n in (129, 112):
    pages = gh(
        f"comments-{n}",
        [
            "api",
            "--paginate",
            "--slurp",
            f"repos/stranske/Doc-Lineage/issues/{n}/comments?per_page=100",
        ],
    )
    for page in pages:
        for c in page:
            for m in re.finditer(
                r"<!-- (runner-(?:reservation|completion)):[^ ]+ (.*?) -->", c["body"], re.S
            ):
                payload = m[2]
                raw = (
                    json.loads(base64.b64decode(payload[7:]))
                    if payload.startswith("base64:")
                    else json.loads(payload)
                )
                records.append(
                    {
                        "kind": m[1],
                        "comment_id": c["id"],
                        "raw": raw,
                        "record": raw.get("record", raw),
                    }
                )
gh("source", ["api", "repos/stranske/Doc-Lineage/issues/112"])
gh(
    "inline",
    ["api", "--paginate", "--slurp", "repos/stranske/Doc-Lineage/pulls/129/comments?per_page=100"],
)
gh(
    "reviews",
    ["api", "--paginate", "--slurp", "repos/stranske/Doc-Lineage/pulls/129/reviews?per_page=100"],
)
(OUT / "decoded-all-heads.json").write_text(json.dumps(records, indent=2) + "\n")
reservations = [r["record"] for r in records if r["kind"] == "runner-reservation"]
completions = {
    r["record"]["reservation_id"]: r["record"] for r in records if r["kind"] == "runner-completion"
}
ids = sorted(
    {r["record"]["workflow_attempt_id"] for r in records if r["record"].get("workflow_attempt_id")}
)
for wid in ids:
    repo, run, attempt = wid.rsplit(":", 2)
    d = gh(
        "native-" + run + "-" + attempt,
        [
            "run",
            "view",
            run,
            "--attempt",
            attempt,
            "--repo",
            repo,
            "--json",
            "databaseId,status,conclusion,event,headSha,jobs,url",
        ],
    )
    if d["status"] != "completed" or any(j["status"] != "completed" for j in d["jobs"]):
        raise RuntimeError("PARK nonterminal native " + wid)
    impl = [
        j
        for j in d["jobs"]
        if re.search(r"^(Keepalive next task|Run .* autofix).* / ", j["name"], re.I)
        and j.get("conclusion") != "skipped"
    ]
    if not impl or any(
        j["status"] != "completed"
        or not j.get("conclusion")
        or j.get("completedAt") in (None, "0001-01-01T00:00:00Z")
        for j in impl
    ):
        raise RuntimeError("PARK implementation child absent/pending " + wid)
claims = {}
for issue in (112, 129):
    claim_path = pathlib.Path(
        f"/Users/teacher/.codex/handoff/claims/stranske__doc-lineage_{issue}/meta"
    )
    claims[str(issue)] = json.loads(claim_path.read_text())
assert claims["112"]["agent"] == "opener1155-source112-main2-guardian", claims
assert claims["129"]["run_id"] == "stranske__Doc-Lineage_129-codex-1792244174435183000", claims
creator_path = pathlib.Path(
    "/Users/teacher/.codex/handoff/dispatch-logs/done/stranske__Doc-Lineage_112-codex-1792238404672546000.json"
)
creator = json.loads(creator_path.read_text())
assert creator["rc"] == 0 and creator["release_rc"] == 0
recovery = json.loads(
    pathlib.Path(
        "/Users/teacher/.codex/handoff/dispatch-logs/done/stranske__Doc-Lineage_129-codex-1792242602242037000.json"
    ).read_text()
)
assert recovery["rc"] == 0 and recovery["release_rc"] == 0
(OUT / "first-recovery-terminal.json").write_text(json.dumps(recovery, indent=2))
(OUT / "claims-and-creator.json").write_text(
    json.dumps({"claims": claims, "creator": creator}, indent=2)
)
summary = {
    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    "head": pr["headRefOid"],
    "source_comments_all_pages": True,
    "pr_comments_all_pages": True,
    "all_heads_decoded": True,
    "reservations": len(reservations),
    "completions": len(completions),
    "unmatched": [
        r["reservation_id"] for r in reservations if r["reservation_id"] not in completions
    ],
    "workflow_attempt_ids": ids,
    "gate": "PASS",
    "parent_claim": "directly read expected guardian; retained",
    "parent_pause": "owner-provided; untouched; not independently observed",
    "original_writer": "directly read dispatcher done rc0/release0",
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary))
