"""Segment classification driven by versioned data catalogs."""

import json
import tempfile
from importlib.resources import files
from pathlib import Path

import pytest

from doc_lineage.compare.classify import (
    SegmentPair,
    classify_segment,
    load_class_catalog,
    load_tier_catalog,
)


def test_tier_labels_loaded_from_data_not_branches(tmp_path: Path) -> None:
    """Runtime catalogs and source mirrors agree; classification reads label data."""
    root_data = Path(__file__).resolve().parents[2] / "data"
    packaged_data = files("doc_lineage.compare").joinpath("data")
    for filename in ("segment_tiers.json", "segment_classes.json"):
        mirror = json.loads((root_data / filename).read_text(encoding="utf-8"))
        canonical = json.loads(packaged_data.joinpath(filename).read_text(encoding="utf-8"))
        assert mirror == canonical, f"{filename} source mirror differs from runtime catalog"

    # A different T2 label must flow through the production loader and classifier,
    # rather than merely matching the currently committed English label.
    tier_data = json.loads(packaged_data.joinpath("segment_tiers.json").read_text())
    tier_data["T2"]["label"] = "catalog-defined factual label"
    tier_path = tmp_path / "segment_tiers.json"
    tier_path.write_text(json.dumps(tier_data), encoding="utf-8")
    changed_tiers = load_tier_catalog(tier_path)
    changed_classes = load_class_catalog(root_data / "segment_classes.json", tiers=changed_tiers)
    changed = classify_segment(
        SegmentPair(section_id="risk", prior_text="Prior disclosure", current_text=None),
        tiers=changed_tiers,
        classes=changed_classes,
    )
    assert changed.tier == "T2"
    assert changed.tier_label == "catalog-defined factual label"

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


def test_tier_mapping_override_changes_classified_tier() -> None:
    tiers = load_tier_catalog()
    base_classes = load_class_catalog(tiers=tiers)
    overridden = {
        class_id: {
            "id": definition.id,
            "label": definition.label,
            "description": definition.description,
            "tier": "T2" if class_id == "NEW" else definition.tier,
        }
        for class_id, definition in base_classes.classes.items()
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        catalog_path = Path(tmpdir) / "segment_classes.json"
        catalog_path.write_text(json.dumps(overridden), encoding="utf-8")
        classes = load_class_catalog(catalog_path, tiers=tiers)
    result = classify_segment(
        SegmentPair(section_id="risk", prior_text=None, current_text="New disclosure."),
        tiers=tiers,
        classes=classes,
    )
    assert result.change_type == "NEW"
    assert result.tier == "T2"
    assert result.tier_label == tiers.label_for("T2")


@pytest.mark.parametrize("validate_on_load", [False, True])
def test_catalog_rejects_unknown_tier_in_any_class(tmp_path: Path, validate_on_load: bool) -> None:
    raw = json.loads(files("doc_lineage.compare").joinpath("data/segment_classes.json").read_text())
    raw["DROPPED"]["tier"] = "not-a-tier"
    catalog_path = tmp_path / "classes.json"
    catalog_path.write_text(json.dumps(raw))
    tiers = load_tier_catalog()
    with pytest.raises(ValueError, match="DROPPED.*not-a-tier"):
        classes = load_class_catalog(catalog_path, tiers=tiers if validate_on_load else None)
        classify_segment(SegmentPair("risk", None, "New disclosure."), tiers=tiers, classes=classes)
