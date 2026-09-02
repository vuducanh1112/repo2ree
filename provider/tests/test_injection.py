"""Resolving the executor/tools bundles the provider injects into a bench.

``lifecycle`` tests cover what injection *does* to a `docker run`; this covers
the resolution itself: which manifest fields become bundle fields, how the two
manifests combine into one tool environment, and why the store volume is named
after a digest of what it will contain.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repo2ree_provider_docker.injection import load_injection_bundle


def _write_bundle(root: Path, manifest: dict[str, Any], *, store_paths: list[str] | None = None) -> str:
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps(manifest))
    if store_paths is not None:
        (root / "store-paths").write_text("\n".join(store_paths) + "\n")
    return str(root)


def _exec_bundle(tmp_path: Path, *, name: str = "exec-bundle", exec_path: str = "/nix/store/aaa/bin/exec") -> str:
    return _write_bundle(
        tmp_path / name,
        {
            "schema_version": 1,
            "exec_path": exec_path,
            "workbench_path": "/nix/store/aaa/bin/repo2ree-workbench",
            "pause_path": "/nix/store/bbb/bin/sleep",
        },
        store_paths=["/nix/store/aaa", "/nix/store/bbb"],
    )


def test_no_exec_bundle_means_no_injection(tmp_path: Path) -> None:
    # An image that ships its own /nix needs nothing injected, and the provider
    # signals that by configuring no exec bundle at all.
    assert load_injection_bundle(None, None) is None
    assert load_injection_bundle("", str(tmp_path)) is None


def test_exec_manifest_fields_become_bundle_paths(tmp_path: Path) -> None:
    bundle = load_injection_bundle(_exec_bundle(tmp_path), None)

    assert bundle is not None
    assert bundle.exec_path == "/nix/store/aaa/bin/exec"
    assert bundle.workbench_path == "/nix/store/aaa/bin/repo2ree-workbench"
    assert bundle.pause_path == "/nix/store/bbb/bin/sleep"
    assert bundle.store_sources == ("/nix/store/aaa", "/nix/store/bbb")
    assert bundle.tool_env == {}


def test_tools_manifest_becomes_the_bench_tool_environment(tmp_path: Path) -> None:
    tools = _write_bundle(
        tmp_path / "tools-bundle",
        {
            "schema_version": 1,
            "tools": {"syft": "/nix/store/ccc/bin/syft", "git-lfs": "/nix/store/ddd/bin/git-lfs"},
            "bin_dir": "/nix/store/eee/bin",
            "env": {"SSL_CERT_FILE": "/nix/store/fff/ca-bundle.crt"},
        },
        store_paths=["/nix/store/ccc", "/nix/store/ddd"],
    )

    bundle = load_injection_bundle(_exec_bundle(tmp_path), tools)

    assert bundle is not None
    # Tool names become env vars the executor looks up; a hyphen is not legal in
    # one, so it is folded to an underscore alongside the upcasing.
    assert bundle.tool_env == {
        "REPO2REE_TOOL_SYFT": "/nix/store/ccc/bin/syft",
        "REPO2REE_TOOL_GIT_LFS": "/nix/store/ddd/bin/git-lfs",
        "REPO2REE_TOOLS_BIN": "/nix/store/eee/bin",
        "SSL_CERT_FILE": "/nix/store/fff/ca-bundle.crt",
    }
    # Both closures land in the one store volume, executor paths first.
    assert bundle.store_sources == ("/nix/store/aaa", "/nix/store/bbb", "/nix/store/ccc", "/nix/store/ddd")


def test_a_populated_store_directory_is_copied_wholesale(tmp_path: Path) -> None:
    # The nix build may emit a `store/` tree instead of a path list; then the
    # single directory *is* the source, copied with docker cp's `/.` idiom.
    root = tmp_path / "exec-bundle"
    _write_bundle(root, {"schema_version": 1, "exec_path": "/exec", "pause_path": "/sleep"})
    (root / "store").mkdir()

    bundle = load_injection_bundle(str(root), None)

    assert bundle is not None
    assert bundle.store_sources == (f"{root / 'store'}/.",)


def test_volume_name_is_stable_for_identical_bundles(tmp_path: Path) -> None:
    # The store volume is a cache keyed by its contents: the same bundles must
    # reuse it across provisions, and different ones must never collide in it.
    first = load_injection_bundle(_exec_bundle(tmp_path, name="a"), None)
    same = load_injection_bundle(_exec_bundle(tmp_path, name="b"), None)
    other = load_injection_bundle(_exec_bundle(tmp_path, name="c", exec_path="/nix/store/zzz/bin/exec"), None)

    assert first is not None
    assert same is not None
    assert other is not None
    assert first.volume_name == same.volume_name
    assert first.volume_name.startswith("repo2ree-store-")
    assert first.volume_name != other.volume_name
