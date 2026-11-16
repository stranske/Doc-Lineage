# Issue #182 — `mirror_root: "."` deliberate-break evidence

Linked issue: [stranske/Doc-Lineage#182](https://github.com/stranske/Doc-Lineage/issues/182).

## Mutation (temporary, reverted on branch tip)

File: `src/doc_lineage/render/links.py`, function `_mirror_url`, **lines 61–62**.

Remove the `if root == ".": return quote(blob, safe="/")` branch so published `mirror_root` `"."` again flows into `_relative_path` and raises `ValueError`.

## RED — `pytest tests/render/test_triple_link_resolver.py::test_published_legal_variable_resolves_from_claims_dir -q`

```text
FAILED tests/render/test_triple_link_resolver.py::test_published_legal_variable_resolves_from_claims_dir
ValueError: mirror_root must be a relative POSIX path without traversal
```

## GREEN — same command on branch tip with the special case restored

```text
1 passed in 0.12s
```

Branch tip keeps the production fix; this file records the RED/GREEN transcript only.