"""Execute both Gate write steps against fork token failures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-00-gate.yml"
STATUS_STEP = "Report Gate commit status"
COMMENT_STEP = "Ensure consolidated summary comment"


def _extract_step_script(step_name: str) -> str:
    document = yaml.safe_load(GATE_WORKFLOW.read_text(encoding="utf-8"))
    for job in document["jobs"].values():
        for step in job.get("steps") or []:
            if step.get("name") == step_name:
                return str(step["with"]["script"])
    raise AssertionError(f"{GATE_WORKFLOW} no longer defines {step_name!r}")


def _run_node_harness(
    tmp_path_factory: pytest.TempPathFactory,
    *,
    step_name: str,
    runner_source: str,
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:  # pragma: no cover - host dependent
        message = "node is required to execute the Gate github-script step"
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)

    workdir = tmp_path_factory.mktemp("gate-script")
    step_path = workdir / "step.js"
    step_path.write_text(_extract_step_script(step_name), encoding="utf-8")
    runner_path = workdir / "runner.js"
    runner_path.write_text(runner_source, encoding="utf-8")
    completed = subprocess.run(
        [node, str(runner_path), str(step_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return dict(json.loads(completed.stdout))


STATUS_RUNNER_JS = textwrap.dedent("""
    const fs = require('fs');
    const vm = require('vm');
    const src = fs.readFileSync(process.argv[2], 'utf8');

    function makeError(status, message, headers = {}, responseMessage = null) {
      const error = new Error(message);
      error.status = status;
      error.response = { headers, data: { message: responseMessage } };
      return error;
    }

    async function runCase({ headRepo, baseRepo, error, state }) {
      const failures = [];
      const requests = [];
      const warnings = [];
      const summaryWrites = [];
      const summaryRaw = [];
      const githubStub = {
        rest: {
          repos: {
            createCommitStatus: async (request) => {
              requests.push(request);
              if (error) throw error;
            },
          },
        },
      };
      const summaryStub = {
        addHeading() { return summaryStub; },
        addRaw(text) { summaryRaw.push(String(text)); return summaryStub; },
        async write() { summaryWrites.push('write'); },
      };
      const sandbox = {
        process: {
          env: {
            STATE: state,
            DESCRIPTION: 'all checks passed',
            TARGET_URL: 'https://example.invalid/run',
          },
        },
        console: { log() {} },
        require: () => ({
          createTokenAwareRetry: async () => ({
            withRetry: async (callback) => callback(githubStub),
          }),
        }),
        core: {
          setFailed: (message) => failures.push(String(message)),
          warning: (message) => warnings.push(String(message)),
          summary: summaryStub,
        },
        context: {
          repo: { owner: 'stranske', repo: 'Doc-Lineage' },
          sha: 'basesha',
          payload: {
            pull_request: {
              head: {
                sha: 'headsha',
                label: 'outside-contributor:branch',
                repo: headRepo === null ? null : { full_name: headRepo },
              },
              base: { repo: { full_name: baseRepo } },
            },
          },
        },
        github: githubStub,
      };
      vm.createContext(sandbox);
      let threw = null;
      try {
        await vm.runInContext('(async () => {\\n' + src + '\\n})()', sandbox);
      } catch (error) {
        threw = {
          status: error.status === undefined ? null : error.status,
          message: String(error.message),
        };
      }
      return {
        failures,
        requests,
        warnings,
        summaryWrites: summaryWrites.length,
        summaryRaw,
        threw,
      };
    }

    const FORK = {
      headRepo: 'outside-contributor/Doc-Lineage',
      baseRepo: 'stranske/Doc-Lineage',
    };
    const SAME = {
      headRepo: 'stranske/Doc-Lineage',
      baseRepo: 'stranske/Doc-Lineage',
    };

    (async () => {
      const outcomes = {
        fork_read_only: await runCase({
          ...FORK, state: 'success',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_read_only_failure: await runCase({
          ...FORK, state: 'failure',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_read_only_error: await runCase({
          ...FORK, state: 'error',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_read_only_pending: await runCase({
          ...FORK, state: 'pending',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        deleted_fork_read_only: await runCase({
          headRepo: null, baseRepo: 'stranske/Doc-Lineage', state: 'success',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        same_repo_read_only: await runCase({
          ...SAME, state: 'success',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_unrelated_403: await runCase({
          ...FORK, state: 'success',
          error: makeError(403, 'Repository policy denied this operation'),
        }),
        fork_rate_limit: await runCase({
          ...FORK, state: 'success',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_failure: await runCase({
          ...FORK, state: 'failure',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_error: await runCase({
          ...FORK, state: 'error',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_pending: await runCase({
          ...FORK, state: 'pending',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_response_message: await runCase({
          ...FORK, state: 'success',
          error: makeError(403, 'Forbidden', {}, 'secondary rate limit exceeded'),
        }),
        fork_primary_rate_limit_header: await runCase({
          ...FORK, state: 'success',
          error: makeError(403, 'Forbidden', { 'x-ratelimit-remaining': '0' }),
        }),
        fork_secondary_rate_limit_header: await runCase({
          ...FORK, state: 'success',
          error: makeError(403, 'Forbidden', { 'retry-after': '60' }),
        }),
        fork_server_error: await runCase({
          ...FORK, state: 'success',
          error: makeError(500, 'Internal server error'),
        }),
        happy_path: await runCase({ ...FORK, state: 'success', error: null }),
      };
      process.stdout.write(JSON.stringify(outcomes));
    })();
    """).strip()


@pytest.fixture(scope="module")
def status_outcomes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return _run_node_harness(
        tmp_path_factory,
        step_name=STATUS_STEP,
        runner_source=STATUS_RUNNER_JS,
    )


def test_fork_read_only_403_reports_success(status_outcomes: dict[str, Any]) -> None:
    case = status_outcomes["fork_read_only"]
    assert case["threw"] is None
    assert case["failures"] == []
    assert case["summaryWrites"] == 1
    assert "success" in " ".join(case["summaryRaw"])
    assert "read-only" in " ".join(case["warnings"])


@pytest.mark.parametrize("state", ["failure", "error", "pending"])
def test_fork_read_only_403_fails_closed_for_non_success_verdicts(
    status_outcomes: dict[str, Any], state: str
) -> None:
    case = status_outcomes[f"fork_read_only_{state}"]
    assert case["threw"] is None
    assert case["summaryWrites"] == 1
    assert len(case["failures"]) == 1
    assert f"'{state}'" in case["failures"][0]


def test_deleted_fork_read_only_403_reports_the_verdict(
    status_outcomes: dict[str, Any],
) -> None:
    case = status_outcomes["deleted_fork_read_only"]
    assert case["threw"] is None
    assert case["failures"] == []
    assert case["summaryWrites"] == 1
    assert "outside-contributor:branch" in " ".join(case["warnings"])


def test_same_repo_403_still_fails(status_outcomes: dict[str, Any]) -> None:
    case = status_outcomes["same_repo_read_only"]
    assert case["threw"]["status"] == 403
    assert case["summaryWrites"] == 0
    assert case["failures"] == []


def test_unrelated_fork_403_still_fails(status_outcomes: dict[str, Any]) -> None:
    case = status_outcomes["fork_unrelated_403"]
    assert case["threw"]["status"] == 403
    assert case["summaryWrites"] == 0
    assert case["failures"] == []


def test_all_rate_limit_signals_keep_their_own_path(
    status_outcomes: dict[str, Any],
) -> None:
    for key in (
        "fork_rate_limit",
        "fork_rate_limit_response_message",
        "fork_primary_rate_limit_header",
        "fork_secondary_rate_limit_header",
    ):
        case = status_outcomes[key]
        assert case["threw"] is None
        assert any("Rate limit" in warning for warning in case["warnings"])
        assert case["summaryWrites"] == 0
        assert case["failures"] == []


@pytest.mark.parametrize("state", ["failure", "error", "pending"])
def test_rate_limit_403_fails_closed_for_non_success_verdicts(
    status_outcomes: dict[str, Any], state: str
) -> None:
    case = status_outcomes[f"fork_rate_limit_{state}"]
    assert case["threw"] is None
    assert len(case["failures"]) == 1
    assert f"'{state}'" in case["failures"][0]


def test_non_403_status_errors_still_fail(status_outcomes: dict[str, Any]) -> None:
    assert status_outcomes["fork_server_error"]["threw"]["status"] == 500


def test_successful_status_write_is_silent(status_outcomes: dict[str, Any]) -> None:
    case = status_outcomes["happy_path"]
    assert case["threw"] is None
    assert case["warnings"] == []
    assert case["failures"] == []
    assert case["summaryWrites"] == 0
    assert case["requests"][0]["sha"] == "headsha"


COMMENT_RUNNER_JS = textwrap.dedent("""
    const nodeFs = require('fs');
    const vm = require('vm');
    const src = nodeFs.readFileSync(process.argv[2], 'utf8');

    function makeError(status, message, headers = {}, responseMessage = null) {
      const error = new Error(message);
      error.status = status;
      error.response = { headers, data: { message: responseMessage } };
      return error;
    }

    async function runCase({ headRepo, baseRepo, error }) {
      const warnings = [];
      const summaryRaw = [];
      const summaryStub = {
        addHeading() { return summaryStub; },
        addRaw(text) { summaryRaw.push(String(text)); return summaryStub; },
        async write() { summaryRaw.push('<written>'); },
      };
      const sandbox = {
        process: { env: {} },
        console: { log() {} },
        require: (id) => {
          if (id === 'path') return { resolve: (value) => '/tmp/' + value };
          if (id === 'fs') {
            return {
              existsSync: () => true,
              readFileSync: () => 'GATE SUMMARY BODY',
            };
          }
          return { upsertAnchoredComment: async () => { if (error) throw error; } };
        },
        core: { warning: (message) => warnings.push(String(message)), summary: summaryStub },
        context: {
          repo: { owner: 'stranske', repo: 'Doc-Lineage' },
          payload: {
            pull_request: {
              number: 72,
              head: {
                label: 'outside-contributor:branch',
                repo: headRepo === null ? null : { full_name: headRepo },
              },
              base: { repo: { full_name: baseRepo } },
            },
          },
        },
        github: {},
      };
      vm.createContext(sandbox);
      let threw = null;
      try {
        await vm.runInContext('(async () => {\\n' + src + '\\n})()', sandbox);
      } catch (caught) {
        threw = {
          status: caught.status === undefined ? null : caught.status,
          message: String(caught.message),
        };
      }
      return { warnings, summaryRaw, threw };
    }

    const FORK = {
      headRepo: 'outside-contributor/Doc-Lineage',
      baseRepo: 'stranske/Doc-Lineage',
    };
    const SAME = {
      headRepo: 'stranske/Doc-Lineage',
      baseRepo: 'stranske/Doc-Lineage',
    };

    (async () => {
      const outcomes = {
        fork_read_only: await runCase({
          ...FORK, error: makeError(403, 'Resource not accessible by integration'),
        }),
        deleted_fork_read_only: await runCase({
          headRepo: null, baseRepo: 'stranske/Doc-Lineage',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        same_repo_read_only: await runCase({
          ...SAME, error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_unrelated_403: await runCase({
          ...FORK, error: makeError(403, 'Repository policy denied this operation'),
        }),
        fork_rate_limit: await runCase({
          ...FORK, error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_response_message: await runCase({
          ...FORK, error: makeError(403, 'Forbidden', {}, 'secondary rate limit exceeded'),
        }),
        fork_primary_rate_limit_header: await runCase({
          ...FORK, error: makeError(403, 'Forbidden', { 'x-ratelimit-remaining': '0' }),
        }),
        fork_secondary_rate_limit_header: await runCase({
          ...FORK, error: makeError(403, 'Forbidden', { 'retry-after': '60' }),
        }),
        fork_server_error: await runCase({ ...FORK, error: makeError(500, 'boom') }),
        happy_path: await runCase({ ...FORK, error: null }),
      };
      process.stdout.write(JSON.stringify(outcomes));
    })();
    """).strip()


@pytest.fixture(scope="module")
def comment_outcomes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return _run_node_harness(
        tmp_path_factory,
        step_name=COMMENT_STEP,
        runner_source=COMMENT_RUNNER_JS,
    )


@pytest.mark.parametrize("key", ["fork_read_only", "deleted_fork_read_only"])
def test_comment_fork_read_only_403_falls_back_to_job_summary(
    comment_outcomes: dict[str, Any], key: str
) -> None:
    case = comment_outcomes[key]
    assert case["threw"] is None
    assert any("read-only" in warning for warning in case["warnings"])
    assert "GATE SUMMARY BODY" in " ".join(case["summaryRaw"])
    assert "<written>" in case["summaryRaw"]


def test_comment_same_repo_403_still_fails(comment_outcomes: dict[str, Any]) -> None:
    assert comment_outcomes["same_repo_read_only"]["threw"]["status"] == 403


def test_comment_unrelated_fork_403_still_fails(
    comment_outcomes: dict[str, Any],
) -> None:
    assert comment_outcomes["fork_unrelated_403"]["threw"]["status"] == 403


def test_comment_rate_limit_signals_stay_separate(
    comment_outcomes: dict[str, Any],
) -> None:
    for key in (
        "fork_rate_limit",
        "fork_rate_limit_response_message",
        "fork_primary_rate_limit_header",
        "fork_secondary_rate_limit_header",
    ):
        case = comment_outcomes[key]
        assert case["threw"] is None
        assert any("Rate limit" in warning for warning in case["warnings"])
        assert case["summaryRaw"] == []


def test_comment_non_403_errors_still_fail(comment_outcomes: dict[str, Any]) -> None:
    assert comment_outcomes["fork_server_error"]["threw"]["status"] == 500


def test_comment_happy_path_is_silent(comment_outcomes: dict[str, Any]) -> None:
    case = comment_outcomes["happy_path"]
    assert case["threw"] is None
    assert case["warnings"] == []
    assert case["summaryRaw"] == []
