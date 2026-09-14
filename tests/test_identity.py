"""Content identity and library metadata parsing contracts."""

from pathlib import Path

import pytest

from doc_lineage.identity import compute_identity, parse_path_parts, sha256_bytes


@pytest.mark.parametrize(
    ("relative", "as_of"),
    [
        ("manager_alpha/lpa/2024/terms.pdf", "2024"),
        ("manager_alpha/lpa/2024/archive/terms.pdf", "2024"),
        ("manager_alpha/lpa/2024/archive/2025/terms.pdf", "2025"),
        ("manager_alpha/lpa/2024/archive/terms_2025.pdf", "2024"),
        ("manager_alpha/lpa/terms_2025.pdf", "2025"),
        ("manager_alpha/lpa/terms.pdf", "unknown"),
    ],
)
def test_doc_key_uses_nearest_year_directory_then_filename(
    tmp_path: Path, relative: str, as_of: str
) -> None:
    identity = compute_identity(tmp_path, tmp_path / relative, content=b"abc")
    assert identity.entity_slug == "manager_alpha"
    assert identity.category == "lpa"
    assert identity.as_of == as_of
    assert identity.doc_key == f"manager_alpha/lpa/{as_of}"


def test_identity_hashes_raw_bytes_from_disk_or_supplied_content(tmp_path: Path) -> None:
    path = tmp_path / "manager_alpha" / "lpa" / "terms.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    identity = compute_identity(tmp_path, path)
    assert identity.sha256 == identity.stable_id == expected
    assert compute_identity(tmp_path, path, content=b"abc") == identity
    assert compute_identity(tmp_path, path, content=b"").sha256 == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    path.write_bytes(b"abc\r\n\x00\xff")
    changed = compute_identity(tmp_path, path)
    assert changed.sha256 == sha256_bytes(b"abc\r\n\x00\xff")
    assert changed.stable_id != identity.stable_id
    assert changed.doc_key == identity.doc_key


def test_move_changes_doc_key_but_preserves_content_identity(tmp_path: Path) -> None:
    original = tmp_path / "manager_alpha/lpa/2024/terms.pdf"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"synthetic document")
    before = compute_identity(tmp_path, original)
    renamed = tmp_path / "manager_beta/side_letters/2025/renamed.pdf"
    renamed.parent.mkdir(parents=True)
    original.rename(renamed)
    after = compute_identity(tmp_path, renamed)
    assert after.doc_key == "manager_beta/side_letters/2025"
    assert after.doc_key != before.doc_key
    assert after.stable_id == before.stable_id
    assert after.sha256 == before.sha256


@pytest.mark.parametrize("relative", ["terms.pdf", "manager_alpha/terms.pdf"])
def test_incomplete_library_path_is_rejected(tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError, match="path must be"):
        parse_path_parts(tmp_path, tmp_path / relative)
