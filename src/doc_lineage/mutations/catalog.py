"""Labeled synthetic mutation catalog for deterministic CI ground truth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MutationSpec:
    """One labeled edit applied to a synthetic LPA segment tree."""

    mutation_id: str
    change_class: str
    section_id: str
    find: str
    replace: str


MUTATION_SPECS: tuple[MutationSpec, ...] = (
    MutationSpec(
        mutation_id="management_fee_bump",
        change_class="gate_provision_change",
        section_id="1",
        find="1.75%",
        replace="2.0%",
    ),
)
