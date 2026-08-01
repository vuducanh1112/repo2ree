from __future__ import annotations

from repo2ree_core.domain.primitives import ReePath
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.ree.workspace.inventory import WorkspaceFile
from repo2ree_core.source_repo import (
    derive_source_repo_metadata,
    format_source_size,
    repo_name_from_origin_url,
    total_source_size,
)


def _file(path: str, size: int) -> WorkspaceFile:
    return WorkspaceFile(path=path, kind="source", size=size)


class TestRepoNameFromOriginUrl:
    def test_takes_last_segment_and_strips_git_suffix(self) -> None:
        assert repo_name_from_origin_url("https://github.com/acme/widget.git") == "widget"

    def test_ignores_trailing_slash_and_query(self) -> None:
        assert repo_name_from_origin_url("https://example.com/foo/bar/?ref=main") == "bar"

    def test_empty_when_no_usable_segment(self) -> None:
        assert repo_name_from_origin_url("") == ""


class TestTotalSourceSize:
    def test_sums_sizes(self) -> None:
        assert total_source_size([_file("a", 100), _file("b", 250)]) == 350

    def test_none_when_inventory_is_empty(self) -> None:
        assert total_source_size([]) is None


class TestFormatSourceSize:
    def test_units_and_precision(self) -> None:
        assert format_source_size(512) == "512 B"
        assert format_source_size(2048) == "2 KB"
        assert format_source_size(int(1.4 * 1024 * 1024)) == "1.4 MB"
        assert format_source_size(12 * 1024 * 1024) == "12 MB"


class TestDeriveSourceRepoMetadata:
    def test_downloaded_source_named_after_origin_repo(self) -> None:
        intent = ReeIntent(
            origin_url="https://github.com/acme/widget.git",
            source_type="git",
            swhid="swh:1:dir:abc",
        )
        session = ReeSession(source_available=True, source_acquired_by="download")
        meta = derive_source_repo_metadata(intent, session, [_file("a.py", 10)])
        assert meta.name == "widget"
        assert meta.origin == "https://github.com/acme/widget.git"
        assert meta.source_type == "git"
        assert meta.swhid == "swh:1:dir:abc"
        assert meta.size_bytes == 10
        assert meta.size_label == "10 B"

    def test_uploaded_source_named_after_archive_with_upload_origin(self) -> None:
        intent = ReeIntent()
        session = ReeSession(
            source_available=True,
            source_acquired_by="upload",
            uploaded_archive=ReePath("python-hello-world.tar.gz"),
        )
        meta = derive_source_repo_metadata(intent, session, [])
        assert meta.name == "python-hello-world.tar.gz"
        assert meta.origin == "Upload"
        assert meta.size_bytes is None
        assert meta.size_label is None

    def test_serializes_snake_case(self) -> None:
        intent = ReeIntent(origin_url="https://github.com/acme/widget", source_type="git")
        session = ReeSession(source_available=True, source_acquired_by="download")
        dumped = derive_source_repo_metadata(intent, session, [_file("a.py", 5)]).model_dump()
        assert dumped["source_type"] == "git"
        assert dumped["size_bytes"] == 5
        assert dumped["size_label"] == "5 B"
        assert dumped["acquired_by"] == "download"

    def test_falls_back_to_ree_name(self) -> None:
        meta = derive_source_repo_metadata(ReeIntent(name="my-ree"), ReeSession(), [])
        assert meta.name == "my-ree"
