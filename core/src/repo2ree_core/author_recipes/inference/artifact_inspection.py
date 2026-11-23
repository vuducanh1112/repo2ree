from __future__ import annotations

import json
import tarfile
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import BinaryIO, Literal

from pydantic import BaseModel, ConfigDict, Field

_MAX_MEMBER_BYTES = 8 * 1024 * 1024
_MAX_PYVENV_CFG_BYTES = 64 * 1024


class DockerArchiveInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["docker_archive"] = "docker_archive"
    repo_tags: list[str] = Field(default_factory=list)
    argv: list[str] | None = None
    shell_command: str | None = None


class VenvArchiveInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["venv_archive"] = "venv_archive"
    restore_dir: str | None = None


class UnrecognizedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["unrecognized"] = "unrecognized"
    reason: str = ""


ArtifactInspection = DockerArchiveInspection | VenvArchiveInspection | UnrecognizedArtifact


def inspect_experiment_environment_artifact(stream: BinaryIO) -> ArtifactInspection:
    try:
        with tarfile.open(fileobj=stream, mode="r:*") as tar:
            names = tar.getnames()
            if "manifest.json" in names:
                return _inspect_docker(tar)
            if "index.json" in names:
                return _inspect_oci(tar)
            cfg_name = next((name for name in names if _is_pyvenv_cfg(name)), None)
            if cfg_name is not None:
                return VenvArchiveInspection(restore_dir=_venv_restore_dir(tar, cfg_name))
            return UnrecognizedArtifact(reason="archive matches no known experiment environment kind")
    except (tarfile.TarError, OSError, EOFError) as exc:
        return UnrecognizedArtifact(reason=f"not a readable archive: {type(exc).__name__}")


def _is_pyvenv_cfg(name: str) -> bool:
    return name == "pyvenv.cfg" or name.endswith("/pyvenv.cfg")


def _venv_restore_dir(tar: tarfile.TarFile, cfg_name: str) -> str | None:
    top_dir = PurePosixPath(cfg_name).parent.name
    if not top_dir:
        return None
    raw = _read_member_text(tar, cfg_name, _MAX_PYVENV_CFG_BYTES)
    if raw is None:
        return None
    target = _venv_target_from_command(_pyvenv_command(raw))
    if target is None or not target.startswith("/"):
        return None
    if PurePosixPath(target).name != top_dir:
        return None
    return target


def _pyvenv_command(cfg_text: str) -> str | None:
    for line in cfg_text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip().lower() == "command":
            return value.strip()
    return None


def _venv_target_from_command(command: str | None) -> str | None:
    if not command:
        return None
    tokens = command.split()
    if "venv" not in tokens:
        return None
    for token in tokens[tokens.index("venv") + 1 :]:
        if not token.startswith("-"):
            return token
    return None


def _inspect_docker(tar: tarfile.TarFile) -> ArtifactInspection:
    manifest = _read_json_member(tar, "manifest.json")
    if not isinstance(manifest, list) or not manifest or not isinstance(manifest[0], dict):
        return UnrecognizedArtifact(reason="docker manifest.json is malformed")
    entry = manifest[0]

    repo_tags = _dedupe(str(tag) for tag in entry.get("RepoTags") or [] if isinstance(tag, str) and tag.strip())

    argv: list[str] | None = None
    shell_command: str | None = None
    config_name = entry.get("Config")
    if isinstance(config_name, str):
        config = _read_json_member(tar, config_name)
        argv, shell_command = _config_command(config)

    return DockerArchiveInspection(repo_tags=repo_tags, argv=argv, shell_command=shell_command)


_OCI_IMAGE_NAME_ANNOTATIONS = ("io.containerd.image.name", "org.opencontainers.image.ref.name")
_MAX_OCI_INDEX_DEPTH = 4


def _inspect_oci(tar: tarfile.TarFile) -> ArtifactInspection:
    index = _read_json_member(tar, "index.json")
    if not isinstance(index, dict):
        return UnrecognizedArtifact(reason="OCI index.json is malformed")
    manifests = index.get("manifests")
    if not isinstance(manifests, list) or not manifests:
        return UnrecognizedArtifact(reason="OCI index.json lists no manifests")

    repo_tags = _dedupe(name for descriptor in manifests if (name := _oci_ref_name(descriptor)) is not None)

    argv: list[str] | None = None
    shell_command: str | None = None
    image_manifest = _resolve_oci_image_manifest(tar, manifests)
    if image_manifest is not None:
        config_descriptor = image_manifest.get("config")
        if isinstance(config_descriptor, dict):
            config = _read_blob_json(tar, config_descriptor.get("digest"))
            argv, shell_command = _config_command(config)

    return DockerArchiveInspection(repo_tags=repo_tags, argv=argv, shell_command=shell_command)


def _oci_ref_name(descriptor: object) -> str | None:
    if not isinstance(descriptor, dict):
        return None
    annotations = descriptor.get("annotations")
    if not isinstance(annotations, dict):
        return None
    for key in _OCI_IMAGE_NAME_ANNOTATIONS:
        value = annotations.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_oci_image_manifest(
    tar: tarfile.TarFile, descriptors: list[object], _depth: int = 0
) -> dict[str, object] | None:
    if _depth > _MAX_OCI_INDEX_DEPTH:
        return None
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            continue
        blob = _read_blob_json(tar, descriptor.get("digest"))
        if not isinstance(blob, dict):
            continue
        if isinstance(blob.get("config"), dict):
            return blob
        nested = blob.get("manifests")
        if isinstance(nested, list):
            found = _resolve_oci_image_manifest(tar, nested, _depth + 1)
            if found is not None:
                return found
    return None


def _read_blob_json(tar: tarfile.TarFile, digest: object) -> object:
    if not isinstance(digest, str) or ":" not in digest:
        return None
    algo, _, hexdigest = digest.partition(":")
    if not algo.isalnum() or not hexdigest.isalnum():
        return None
    return _read_json_member(tar, f"blobs/{algo}/{hexdigest}")


def _config_command(config: object) -> tuple[list[str] | None, str | None]:
    if not isinstance(config, dict):
        return None, None
    image_config = config.get("config") or config.get("Config")
    if not isinstance(image_config, dict):
        return None, None

    entrypoint = image_config.get("Entrypoint")
    cmd = image_config.get("Cmd")

    if isinstance(entrypoint, str) and entrypoint.strip():
        return None, entrypoint
    if entrypoint is None and isinstance(cmd, str) and cmd.strip():
        return None, cmd

    parts: list[str] = []
    for value in (entrypoint, cmd):
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            parts.extend(value)
    return (parts or None), None


def _read_member_bytes(tar: tarfile.TarFile, name: str, max_bytes: int) -> bytes | None:
    try:
        member = tar.getmember(name)
    except KeyError:
        return None
    if not member.isfile() or member.size > max_bytes:
        return None
    extracted = tar.extractfile(member)
    if extracted is None:
        return None
    try:
        return extracted.read(max_bytes)
    except OSError:
        return None


def _read_json_member(tar: tarfile.TarFile, name: str) -> object:
    data = _read_member_bytes(tar, name, _MAX_MEMBER_BYTES)
    if data is None:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None


def _read_member_text(tar: tarfile.TarFile, name: str, max_bytes: int) -> str | None:
    data = _read_member_bytes(tar, name, max_bytes)
    if data is None:
        return None
    try:
        return data.decode("utf-8", errors="replace")
    except ValueError:
        return None


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
