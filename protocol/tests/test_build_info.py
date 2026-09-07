from repo2ree_protocol.build import BUILD_REVISION_ENV, current_build


def test_current_build_reads_injected_revision(monkeypatch) -> None:
    monkeypatch.setenv(BUILD_REVISION_ENV, "0123456789abcdef-dirty")

    build = current_build("distribution-that-does-not-exist")

    assert build.version == ""
    assert build.revision == "0123456789abcdef-dirty"
