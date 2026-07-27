"""Focused tests for runtime-artifact inspection.

Docker/venv classification is exercised end-to-end by the activation and
experiment suites; this pins the subtler venv ``restore_dir`` recovery — a venv
bakes absolute paths, so restoring it to the wrong directory silently breaks it,
and the recovered path must be trusted only when it is safe to.
"""

from __future__ import annotations

import io

from scriptinfer_helpers import docker_archive, not_an_archive, oci_archive, venv_archive

from repo2ree_core.authoring.script_inference.artifact_inspection import (
    DockerArchiveInspection,
    UnrecognizedArtifact,
    VenvArchiveInspection,
    inspect_runtime_artifact,
)


def _inspect(data: bytes):
    return inspect_runtime_artifact(io.BytesIO(data))


def test_venv_without_command_has_no_restore_dir() -> None:
    inspection = _inspect(venv_archive())
    assert isinstance(inspection, VenvArchiveInspection)
    # No ``command`` line -> nothing to recover; caller falls back to the default.
    assert inspection.restore_dir is None


def test_venv_command_recovers_absolute_restore_dir() -> None:
    inspection = _inspect(venv_archive(top_dir="ree-venv", command="/usr/bin/python3 -m venv /opt/envs/ree-venv"))
    assert isinstance(inspection, VenvArchiveInspection)
    assert inspection.restore_dir == "/opt/envs/ree-venv"


def test_venv_command_with_flags_before_the_dir() -> None:
    inspection = _inspect(venv_archive(top_dir="ree-venv", command="/usr/bin/python3 -m venv --copies /opt/ree-venv"))
    assert isinstance(inspection, VenvArchiveInspection)
    assert inspection.restore_dir == "/opt/ree-venv"


def test_venv_restore_dir_rejected_when_basename_mismatches_top_dir() -> None:
    # The archive packs ``ree-venv/`` but the command targets ``other`` — a
    # ``tar -C`` restore would not land at that path, so we must not trust it.
    inspection = _inspect(venv_archive(top_dir="ree-venv", command="/usr/bin/python3 -m venv /opt/other"))
    assert isinstance(inspection, VenvArchiveInspection)
    assert inspection.restore_dir is None


def test_venv_relative_command_dir_is_rejected() -> None:
    inspection = _inspect(venv_archive(top_dir="ree-venv", command="python -m venv ree-venv"))
    assert isinstance(inspection, VenvArchiveInspection)
    assert inspection.restore_dir is None


def test_venv_cfg_at_archive_root_has_no_top_dir() -> None:
    inspection = _inspect(venv_archive(top_dir=".", command="python -m venv /tmp/x"))
    assert isinstance(inspection, VenvArchiveInspection)
    assert inspection.restore_dir is None


def test_docker_archive_is_classified() -> None:
    inspection = _inspect(docker_archive(["ree-runtime:demo"]))
    assert isinstance(inspection, DockerArchiveInspection)
    assert inspection.repo_tags == ["ree-runtime:demo"]


def test_oci_archive_is_classified_as_docker() -> None:
    # A containerd-image-store ``docker save`` (OCI layout, no manifest.json) must
    # classify exactly like the legacy layout so activation/experiment resolve.
    inspection = _inspect(oci_archive("ree-runtime:demo", entrypoint=["python"], cmd=["main.py"]))
    assert isinstance(inspection, DockerArchiveInspection)
    assert inspection.repo_tags == ["ree-runtime:demo"]
    assert inspection.argv == ["python", "main.py"]


def test_oci_multi_arch_index_resolves_the_config_command() -> None:
    # The index points at a nested platform index; inspection descends to the
    # image manifest to read its declared command.
    inspection = _inspect(oci_archive("ree-runtime:demo", cmd=["run.py"], multi_arch=True))
    assert isinstance(inspection, DockerArchiveInspection)
    assert inspection.repo_tags == ["ree-runtime:demo"]
    assert inspection.argv == ["run.py"]


def test_oci_archive_without_a_ref_has_no_repo_tags() -> None:
    # An untagged export declares no image name; downstream this is "no usable
    # image reference", not a resolved runtime.
    inspection = _inspect(oci_archive(None))
    assert isinstance(inspection, DockerArchiveInspection)
    assert inspection.repo_tags == []


def test_non_archive_is_unrecognized_and_never_raises() -> None:
    assert isinstance(_inspect(not_an_archive()), UnrecognizedArtifact)
