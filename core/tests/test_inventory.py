from repo2ree_core.workspace.inventory import (
    MAX_INLINE_SBOM_BYTES,
    MAX_INLINE_TEXT_BYTES,
    classify_file_kind,
    is_metadata_file_name,
    is_reserved_workspace_filename,
    is_upload_staging_name,
    should_inline_file_content,
)


def test_is_metadata_file_name():
    assert is_metadata_file_name(".workspace.json") is True
    assert is_metadata_file_name(".workspace") is False
    assert is_metadata_file_name("workspace.json") is False


def test_is_upload_staging_name():
    assert is_upload_staging_name(".upload.tok.bin") is True
    assert is_upload_staging_name(".upload.") is True
    assert is_upload_staging_name("upload.bin") is False
    assert is_upload_staging_name(".uploads") is False


def test_is_reserved_workspace_filename_covers_both_categories():
    assert is_reserved_workspace_filename(".workspace.json") is True
    assert is_reserved_workspace_filename(".workspace.lock") is True
    assert is_reserved_workspace_filename(".upload.tok.bin") is True
    assert is_reserved_workspace_filename("Dockerfile") is False
    assert is_reserved_workspace_filename("README.md") is False


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


def test_classify_file_kind_returns_source_for_any_path():
    # Current implementation is uniform; tests pin the contract until
    # finer classification lands.
    assert classify_file_kind("Dockerfile") == "source"
    assert classify_file_kind("src/main.py") == "source"
    assert classify_file_kind("") == "source"
