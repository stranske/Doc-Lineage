# Issue #74 — Gate fork-token deliberate-break evidence

Captured at `2026-09-29T10:11:09Z` from `main` commit
`b5697ea35feb83e9e56f9580a798792c48b38976` (merged PR #73).

The deliberate break replaced only both `readOnlyForkToken` predicates in
`.github/workflows/pr-00-gate.yml` with `false`. No test code was changed.

## RED — fork fallbacks disabled

Command:

```console
$ python3 -m pytest tests/test_gate_commit_status_fork_tolerance.py -q
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/teacher/.codex/automations/pd-workloop-resume/worktrees/Doc-Lineage-issue-74
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 20 items

tests/test_gate_commit_status_fork_tolerance.py FFFFF........FF.....     [100%]

=================================== FAILURES ===================================
___________________ test_fork_read_only_403_reports_success ____________________

    def test_fork_read_only_403_reports_success(status_outcomes: dict[str, Any]) -> None:
        case = status_outcomes["fork_read_only"]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:236: AssertionError
____ test_fork_read_only_403_fails_closed_for_non_success_verdicts[failure] ____

    @pytest.mark.parametrize("state", ["failure", "error", "pending"])
    def test_fork_read_only_403_fails_closed_for_non_success_verdicts(
        status_outcomes: dict[str, Any], state: str
    ) -> None:
        case = status_outcomes[f"fork_read_only_{state}"]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:248: AssertionError
_____ test_fork_read_only_403_fails_closed_for_non_success_verdicts[error] _____

    @pytest.mark.parametrize("state", ["failure", "error", "pending"])
    def test_fork_read_only_403_fails_closed_for_non_success_verdicts(
        status_outcomes: dict[str, Any], state: str
    ) -> None:
        case = status_outcomes[f"fork_read_only_{state}"]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:248: AssertionError
____ test_fork_read_only_403_fails_closed_for_non_success_verdicts[pending] ____

    @pytest.mark.parametrize("state", ["failure", "error", "pending"])
    def test_fork_read_only_403_fails_closed_for_non_success_verdicts(
        status_outcomes: dict[str, Any], state: str
    ) -> None:
        case = status_outcomes[f"fork_read_only_{state}"]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:248: AssertionError
_____________ test_deleted_fork_read_only_403_reports_the_verdict ______________

    def test_deleted_fork_read_only_403_reports_the_verdict(
        status_outcomes: dict[str, Any],
    ) -> None:
        case = status_outcomes["deleted_fork_read_only"]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:258: AssertionError
__ test_comment_fork_read_only_403_falls_back_to_job_summary[fork_read_only] ___

    @pytest.mark.parametrize("key", ["fork_read_only", "deleted_fork_read_only"])
    def test_comment_fork_read_only_403_falls_back_to_job_summary(
        comment_outcomes: dict[str, Any], key: str
    ) -> None:
        case = comment_outcomes[key]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:437: AssertionError
_ test_comment_fork_read_only_403_falls_back_to_job_summary[deleted_fork_read_only] _

    @pytest.mark.parametrize("key", ["fork_read_only", "deleted_fork_read_only"])
    def test_comment_fork_read_only_403_falls_back_to_job_summary(
        comment_outcomes: dict[str, Any], key: str
    ) -> None:
        case = comment_outcomes[key]
>       assert case["threw"] is None
E       AssertionError: assert {'status': 403, 'message': 'Resource not accessible by integration'} is None

tests/test_gate_commit_status_fork_tolerance.py:437: AssertionError
=========================== short test summary info ============================
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_reports_success
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_fails_closed_for_non_success_verdicts[failure]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_fails_closed_for_non_success_verdicts[error]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_fork_read_only_403_fails_closed_for_non_success_verdicts[pending]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_deleted_fork_read_only_403_reports_the_verdict
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_comment_fork_read_only_403_falls_back_to_job_summary[fork_read_only]
FAILED tests/test_gate_commit_status_fork_tolerance.py::test_comment_fork_read_only_403_falls_back_to_job_summary[deleted_fork_read_only]
========================= 7 failed, 13 passed in 0.55s =========================
```

Exit status: `1`.

## GREEN — exact restoration

After restoring `.github/workflows/pr-00-gate.yml` exactly:

```console
$ python3 -m pytest tests/test_gate_commit_status_fork_tolerance.py -q
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/teacher/.codex/automations/pd-workloop-resume/worktrees/Doc-Lineage-issue-74
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 20 items

tests/test_gate_commit_status_fork_tolerance.py ....................     [100%]

============================== 20 passed in 0.55s ==============================
```

Exit status: `0`.

The final production/test-tree restoration check also passed:

```console
$ git diff --exit-code HEAD -- .github/workflows/pr-00-gate.yml tests/test_gate_commit_status_fork_tolerance.py
```

Exit status: `0`; no output. The committed change is evidence-only.
