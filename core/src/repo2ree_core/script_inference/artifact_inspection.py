"""Read-only inspection of a built runtime artifact.

Turns a runtime archive's bytes into a small typed fact: is it a Docker archive
(and what image references / config commands does it declare), a packed Python
venv, or unrecognized. It reads only the manifest and config *members* — never
loading the whole (possibly multi-hundred-MB) image into memory and never
extracting to disk — and applies the same bounded-size and safe-name spirit as
``storage/extract.py``.

Both ``docker save`` shapes are recognized: the legacy layout (a root
``manifest.json``, the default with dockerd's own image store) and the OCI layout
(a root ``index.json`` + ``blobs/``, what a containerd-image-store daemon or
``buildx --output type=oci`` emits). Both classify as a Docker archive; only the
member layout differs, so the runtime-command fork downstream is unchanged.

This is pure evidence extraction. Selecting a command is a downstream decision;
inspection only reports what the archive declares.
"""

from __future__ import annotations

import json
import tarfile
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import BinaryIO, Literal

from pydantic import BaseModel, ConfigDict, Field

# A single archive member we are willing to read fully (manifest.json / config).
_MAX_MEMBER_BYTES = 8 * 1024 * 1024
# ``pyvenv.cfg`` is a handful of lines; cap it far tighter than a docker config.
_MAX_PYVENV_CFG_BYTES = 64 * 1024


class DockerArchiveInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["docker_archive"] = "docker_archive"
    # De-duplicated, order-preserving usable image references from RepoTags.
    repo_tags: list[str] = Field(default_factory=list)
    # Combined exec-form argv (Entrypoint + Cmd), when both are JSON/exec form.
    argv: list[str] | None = None
    # A shell-form Entrypoint/Cmd string, returned verbatim (never rewritten).
    shell_command: str | None = None


class VenvArchiveInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["venv_archive"] = "venv_archive"
    # The absolute directory the venv was built at, recovered from its own
    # ``pyvenv.cfg`` ``command`` line, when the archive packs it under a matching
    # top-level directory. ``None`` when it cannot be established safely, and the
    # caller falls back to the repo2ree default build location.
    restore_dir: str | None = None


class UnrecognizedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["unrecognized"] = "unrecognized"
    reason: str = ""


ArtifactInspection = DockerArchiveInspection | VenvArchiveInspection | UnrecognizedArtifact


def inspect_runtime_artifact(stream: BinaryIO) -> ArtifactInspection:
    """Classify a runtime archive from a seekable binary stream.

    Recognizes both ``docker save`` layouts — legacy (root ``manifest.json``) and
    OCI (root ``index.json`` + ``blobs/``) — and a gzipped venv tarball (contains a
    ``pyvenv.cfg``). Anything else — not a tar, unreadable, or an unrecognized
    shape — is ``unrecognized`` and never raises.
    """
    try:
        # "r:*" transparently handles the venv's gzip and the image's plain tar.
        with tarfile.open(fileobj=stream, mode="r:*") as tar:
            names = tar.getnames()
            if "manifest.json" in names:
                return _inspect_docker(tar)
            if "index.json" in names:
                return _inspect_oci(tar)
            cfg_name = next((name for name in names if _is_pyvenv_cfg(name)), None)
            if cfg_name is not None:
                return VenvArchiveInspection(restore_dir=_venv_restore_dir(tar, cfg_name))
            return UnrecognizedArtifact(reason="archive matches no known runtime kind")
    except (tarfile.TarError, OSError, EOFError) as exc:
        return UnrecognizedArtifact(reason=f"not a readable archive: {type(exc).__name__}")


def _is_pyvenv_cfg(name: str) -> bool:
    # ``pyvenv.cfg`` sits at the venv root, i.e. ``<venv>/pyvenv.cfg``.
    return name == "pyvenv.cfg" or name.endswith("/pyvenv.cfg")


def _venv_restore_dir(tar: tarfile.TarFile, cfg_name: str) -> str | None:
    """The absolute path the venv must be restored to, from its ``pyvenv.cfg``.

    A venv bakes absolute paths, so it must be restored exactly where it was
    built. Python records that path in the ``command`` line
    (``... -m venv <dir>``). We trust it only when it is absolute *and* its
    basename matches the archive's own top-level directory — because the restore
    unpacks with ``tar -C <parent>`` and so lands at ``<parent>/<top-dir>``. When
    they disagree (or no ``command`` is present) we return ``None`` rather than
    guess, and the caller uses the repo2ree default location.
    """
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
    """The venv directory argument of a ``python -m venv <dir>`` command line."""
    if not command:
        return None
    tokens = command.split()
    if "venv" not in tokens:
        return None
    # The first non-flag token after ``venv`` is the target directory.
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


# Annotation keys an OCI ``index.json`` carries an image's reference under, most
# specific first: containerd (dockerd's OCI export) records the full ``name:tag``;
# the OCI standard key often holds just the tag. One name per manifest descriptor,
# so a single-image export yields a single ref (not a false "multiple images").
_OCI_IMAGE_NAME_ANNOTATIONS = ("io.containerd.image.name", "org.opencontainers.image.ref.name")
# Bound on how deep a nested OCI index (multi-arch) is followed to an image
# manifest — a self-referential index cannot spin this into an unbounded walk.
_MAX_OCI_INDEX_DEPTH = 4


def _inspect_oci(tar: tarfile.TarFile) -> ArtifactInspection:
    """Classify an OCI-layout ``docker save`` tar (root ``index.json`` + blobs).

    Reads the image references off the index's manifest annotations and follows
    one manifest (descending through a multi-arch sub-index if present) to its
    config blob for the declared Entrypoint/Cmd. Never reads a layer blob.
    """
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
    """The first image manifest (a blob with a ``config``) reachable from these
    descriptors, descending through nested indexes up to a bounded depth."""
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
    """Read and parse an OCI blob addressed by its ``<algo>:<hex>`` digest.

    The digest names the member ``blobs/<algo>/<hex>``; reject anything that is
    not a plain algo/hex pair so a crafted digest cannot escape ``blobs/``.
    """
    if not isinstance(digest, str) or ":" not in digest:
        return None
    algo, _, hexdigest = digest.partition(":")
    if not algo.isalnum() or not hexdigest.isalnum():
        return None
    return _read_json_member(tar, f"blobs/{algo}/{hexdigest}")


def _config_command(config: object) -> tuple[list[str] | None, str | None]:
    """Combine an image config's Entrypoint/Cmd into a suggested command.

    Exec (JSON list) forms concatenate as ``Entrypoint + Cmd``. A shell-form
    (string) Entrypoint/Cmd is returned verbatim and never rewritten into argv.
    """
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
