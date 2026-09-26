# Deliberate-break evidence: DOCX redline renderer gate (#45 / #15)

Linked issue: `stranske/Doc-Lineage#45` (implementation parent `#15`, merged as PR #22).

## Mutation (temporary, reverted before merge)

In `src/doc_lineage/export/docx_redline.py::export_docx_redline`, the Docxodus engine call was temporarily bypassed so the helper returned the unmarked `modified` bytes with no `w:ins` / `w:del` revision markup.

Production code on this branch still runs `DocxodusEngine().run_redline`; this file records the RED/GREEN transcript only.

## RED — `pytest tests/export/test_docx_redline_golden.py::test_tracked_changes_present -q`

```
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: .
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/export/test_docx_redline_golden.py F                               [100%]

=================================== FAILURES ===================================
_________________________ test_tracked_changes_present _________________________

engine_cache = None

    def test_tracked_changes_present(engine_cache: None) -> None:
        ...
        insertions = document.findall(".//w:ins", NS)
        deletions = document.findall(".//w:del", NS)
>       assert insertions, "Expected native Word insertion markup"
E       AssertionError: Expected native Word insertion markup
E       assert []

tests/export/test_docx_redline_golden.py:103: AssertionError
=========================== short test summary info ============================
FAILED tests/export/test_docx_redline_golden.py::test_tracked_changes_present
============================== 1 failed in 9.79s ===============================
```

## GREEN — same command after revert

```
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: .
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/export/test_docx_redline_golden.py .                               [100%]

============================== 1 passed in 22.65s ===============================
```

## Verification command (this PR)

`pytest tests/export/test_docx_redline_golden.py::test_tracked_changes_present -q`
