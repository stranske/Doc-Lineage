# Deliberate-break evidence: section-ID blackline gate (#38 / #10)

Linked issue: `stranske/Doc-Lineage#38` (parent gate `#10`).

## Mutation (temporary, reverted before merge)

File: `src/doc_lineage/blackline.py`, function `align_sections`, **lines 140–169** (the `for section_id in ordered_ids:` loop body through `return pairs`).

The ID-first loop was temporarily replaced with positional index pairing and reversed right-side order, while still labeling `pairing_method="section_id"` (mislabeled semantic-only pairing):

```python
    left_sections = list(doc_a.sections)
    right_sections = list(doc_b.sections)
    pairs: list[SectionPair] = []
    for index, section_id in enumerate(ordered_ids):
        left = left_sections[index] if index < len(left_sections) else None
        right = right_sections[-(index + 1)] if index < len(right_sections) else None
        confidence = min(
            _finite_confidence(left.header_confidence if left is not None else 1.0),
            _finite_confidence(right.header_confidence if right is not None else 1.0),
        )
        pairs.append(
            SectionPair(
                section_id=section_id,
                left=left,
                right=right,
                pairing_method="section_id",  # deliberate-break: mislabels positional pairing
                confidence=confidence,
            )
        )
    return pairs
```

Production code on this branch keeps ID-first pairing (`blackline.py` lines 140–169 as merged); this file records the RED/GREEN transcript only.

## RED — `pytest tests/blackline/test_section_id_pairing.py::test_pairs_by_section_id -q`

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/teacher/.codex/automations/pd-workloop-resume/worktrees/Doc-Lineage-issue-38
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/blackline/test_section_id_pairing.py F                             [100%]

=================================== FAILURES ===================================
___________________________ test_pairs_by_section_id ___________________________

    def test_pairs_by_section_id() -> None:
        """Named gate: numbered sections pair by stable section IDs on a golden pair."""
        before = _load_fixture("lpa_before_segments.json")
        after = _load_fixture("lpa_after_segments.json")
        doc_a = build_section_tree(before.segments, source_sha256=before.source_sha256)
        doc_b = build_section_tree(after.segments, source_sha256=after.source_sha256)
    
        pairs = align_sections(doc_a, doc_b)
        assert [pair.section_id for pair in pairs] == ["1", "2", "3", "4"]
        assert all(pair.pairing_method == "section_id" for pair in pairs)
        assert all(pair.left is not None and pair.right is not None for pair in pairs)
        assert pairs[0].left is not None and pairs[0].right is not None
        assert pairs[0].left.text != pairs[0].right.text
        assert pairs[1].left is not None and pairs[1].right is not None
>       assert pairs[1].left.text == pairs[1].right.text
E       AssertionError: assert '2. CARRIED I...ded annually.' == '3. KEY PERSO... Partnership.'
E         
E         - 3. KEY PERSON EVENT A Key Person Event occurs if fewer than two Key Persons devote substantially all business time to the Partnership.
E         + 2. CARRIED INTEREST Carried interest is 20% of Distributable Proceeds, subject to a preferred return of 8% compounded annually.

tests/blackline/test_section_id_pairing.py:80: AssertionError
=========================== short test summary info ============================
FAILED tests/blackline/test_section_id_pairing.py::test_pairs_by_section_id
============================== 1 failed in 2.82s ===============================
```

## GREEN — same command after revert

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/teacher/.codex/automations/pd-workloop-resume/worktrees/Doc-Lineage-issue-38
configfile: pyproject.toml
plugins: langsmith-0.10.9, cov-7.1.0, xdist-3.8.0, rerunfailures-16.3, datadir-1.8.0, typeguard-4.5.1, asyncio-1.3.0, pytest_httpserver-1.1.3, hypothesis-6.155.7, regressions-2.11.0, Faker-40.39.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/blackline/test_section_id_pairing.py .                             [100%]

============================== 1 passed in 4.42s ===============================
```

## Verification command (this PR)

`pytest tests/blackline/test_section_id_pairing.py::test_pairs_by_section_id -q`
