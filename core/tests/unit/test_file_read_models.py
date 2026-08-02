import pytest

from repo2ree_core.operations.read_models.files import (
    MAX_INLINE_SBOM_BYTES,
    MAX_INLINE_TEXT_BYTES,
    classify_workspace_file_kind,
    read_ree_file_bytes,
    should_inline_file_content,
)
from repo2ree_core.persistence.layout import ReeLayout


def test_should_inline_file_content_default_threshold():
    assert should_inline_file_content("a.txt", 0) is True
    assert should_inline_file_content("a.txt", MAX_INLINE_TEXT_BYTES) is True
    assert should_inline_file_content("a.txt", MAX_INLINE_TEXT_BYTES + 1) is False


def test_should_inline_file_content_sbom_uses_higher_threshold():
    just_over_text = MAX_INLINE_TEXT_BYTES + 1
    just_under_sbom = MAX_INLINE_SBOM_BYTES
    assert should_inline_file_content("sbom.json", just_over_text) is False
    # the smaller cap fires first for any size > MAX_INLINE_TEXT_BYTES even
    # when the sbom-specific cap is higher; the function is conservative
    assert should_inline_file_content("sbom.json", just_under_sbom) is False
    assert should_inline_file_content("sbom.json", MAX_INLINE_TEXT_BYTES) is True


def test_should_inline_file_content_sbom_oversize_excluded():
    assert should_inline_file_content("nested/sbom.json", MAX_INLINE_SBOM_BYTES + 1) is False


def test_should_inline_file_content_case_insensitive_sbom_match():
    assert should_inline_file_content("path/SBOM.JSON", MAX_INLINE_SBOM_BYTES + 1) is False


def test_classify_workspace_file_kind_returns_source_for_any_path():
    # Current implementation is uniform; tests pin the contract until
    # finer classification lands.
    assert classify_workspace_file_kind("Dockerfile") == "source"
    assert classify_workspace_file_kind("src/main.py") == "source"
    assert classify_workspace_file_kind("") == "source"


def test_read_ree_file_bytes_uses_ree_relative_paths(tmp_path):
    layout = ReeLayout.for_ree(tmp_path, "ree-1")
    layout.artifacts.mkdir(parents=True)
    layout.sbom.write_bytes(b"sbom")

    assert read_ree_file_bytes(tmp_path, "ree-1", "artifacts/sbom.json") == b"sbom"


def test_read_ree_file_bytes_rejects_escape(tmp_path):
    layout = ReeLayout.for_ree(tmp_path, "ree-1")
    layout.root.mkdir(parents=True)

    with pytest.raises(ValueError, match="Invalid REE file path"):
        read_ree_file_bytes(tmp_path, "ree-1", "../outside")
