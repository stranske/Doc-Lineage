"""Segment classification driven by versioned data catalogs."""

from doc_lineage.compare.classify import (
    SegmentPair,
    classify_segment,
    load_class_catalog,
    load_tier_catalog,
)


def test_tier_labels_loaded_from_data_not_branches() -> None:
    tiers = load_tier_catalog()
    classes = load_class_catalog()
    result = classify_segment(
        SegmentPair(
            section_id="reporting",
            prior_text="Reports are delivered each quarter to investors.",
            current_text="Reports are delivered quarterly to investors.",
        ),
        tiers=tiers,
        classes=classes,
    )
    assert result.tier == "T3"
    assert result.tier_label == tiers.label_for("T3")
    assert result.tier_label == "cosmetic"
    assert result.change_type == "NEAR_VERBATIM"


def test_new_segment_classified_from_data() -> None:
    tiers = load_tier_catalog()
    classes = load_class_catalog()
    result = classify_segment(
        SegmentPair(section_id="risk", prior_text=None, current_text="New disclosure."),
        tiers=tiers,
        classes=classes,
    )
    assert result.change_type == "NEW"
    assert result.class_label == classes.label_for("NEW")


def test_explicit_removal_classified_as_dropped() -> None:
    tiers = load_tier_catalog()
    classes = load_class_catalog()
    result = classify_segment(
        SegmentPair(
            section_id="old_clause",
            prior_text="This clause is removed.",
            current_text=None,
            explicit_removal=True,
        ),
        tiers=tiers,
        classes=classes,
    )
    assert result.change_type == "DROPPED"
    assert result.tier == "T1"


def test_verbatim_exact_equality() -> None:
    tiers = load_tier_catalog()
    classes = load_class_catalog()
    long_text = "A" * 1000
    result = classify_segment(
        SegmentPair(
            section_id="long_segment",
            prior_text=long_text,
            current_text=long_text,
        ),
        tiers=tiers,
        classes=classes,
    )
    assert result.change_type == "VERBATIM"


def test_verbatim_one_char_change_not_verbatim() -> None:
    tiers = load_tier_catalog()
    classes = load_class_catalog()
    long_text = "A" * 1000
    modified_text = "A" * 999 + "B"
    result = classify_segment(
        SegmentPair(
            section_id="long_segment",
            prior_text=long_text,
            current_text=modified_text,
        ),
        tiers=tiers,
        classes=classes,
    )
    assert result.change_type == "NEAR_VERBATIM"
    assert result.change_type != "VERBATIM"
