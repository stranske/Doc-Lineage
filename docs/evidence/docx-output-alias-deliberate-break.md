# DOCX output alias verification

Verified on 2026-10-17 with Python 3.14.8 and pytest 9.1.1.

## Completed tasks and acceptance criteria

- [x] Check `Path.resolve()` and `os.path.samefile` before calling the exporter;
  reject aliases with exit code 1 and the specified error message.
- [x] Check before writing, while allowing a destination that does not yet exist.
- [x] Test output equal to each input, checking both SHA-256 digests and stderr.
- [x] Test relative/absolute paths, symbolic links, and hard links to both inputs;
  skip unsupported link operations. Also test paths containing `..`.
- [x] Confirm README states that aliasing destinations are rejected.
- [x] Confirm the exporter docstring states it never writes to either input path.
- [x] Pass `pytest tests/test_cli.py -k export -m "not slow"`: 16 passed,
  4 deselected, no skips.
- [x] Remove the guard temporarily and confirm the direct-original test fails
  because the original hash changes; restore the guard afterward.
- [x] Pass the existing distinct-output and stdout tests without changing them.
- [x] Pass `pytest tests/export/test_docx_redline_golden.py -m "not slow"`:
  9 passed, including reject-all and accept-all text recovery.

## Deliberate-break result

Temporarily removed the `if args.output is not None` guard block from
`_run_export_docx`, leaving the exporter call and output write in place. Ran:

```bash
pytest 'tests/test_cli.py::test_export_rejects_input_alias_without_changing_hashes[direct-original]' -m "not slow"
```

The test failed at the input hash assertion, before checking the exit code:

```text
E       AssertionError: assert [...] == [...]
E       At index 0 diff:
        actual:   f4b13b20e1e84f878f28cb81e4387aa7c6e44e479a7fa15aa8a00a6053c63f7c
        expected: 93661baf228df3c3f1514a731dcd708c6685d0334a992b0f72bc5511a6117692
1 failed
```

The original source bytes were restored in a `finally` block. The combined
verification after restoration passed:

```bash
pytest tests/test_cli.py tests/export/test_docx_redline_golden.py -m "not slow"
# 29 passed
```

Black's repository-wide check passed for all 158 Python files. To avoid the
sandbox's worker-process restriction and event-loop hang, each file was first
checked separately with `BLACK_CACHE_DIR=/tmp/doc-lineage-black-cache`, then
the full check ran with that cache and `BLACK_NUM_WORKERS=1`:

```bash
black --check --line-length 100 --exclude '(\.workflows-lib|node_modules)' .
# 158 files would be left unchanged.
```

`ruff check src/doc_lineage/cli.py tests/test_cli.py` and `git diff --check`
also passed.
