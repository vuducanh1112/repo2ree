"""Shared fixtures for activation/experiment script-inference tests.

An in-memory ``ArtifactAccessor`` plus builders for the two runtime archive
shapes inference inspects: a Docker ``docker save`` tar (manifest.json +
config) and a packed-venv gzip tarball (pyvenv.cfg).
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile

from repo2ree_core.authoring.script_inference.runtime_inputs import ArtifactFile


def docker_archive(repo_tags: list[str], *, entrypoint: object = None, cmd: object = None) -> bytes:
    config: dict[str, object] = {}
    if entrypoint is not None:
        config["Entrypoint"] = entrypoint
    if cmd is not None:
        config["Cmd"] = cmd
    config_bytes = json.dumps({"config": config}).encode()
    manifest = json.dumps([{"Config": "config.json", "RepoTags": repo_tags, "Layers": []}]).encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in (("manifest.json", manifest), ("config.json", config_bytes)):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def oci_archive(
    image_ref: str | None,
    *,
    entrypoint: object = None,
    cmd: object = None,
    multi_arch: bool = False,
) -> bytes:
    """An OCI-layout ``docker save`` tar: root ``index.json`` + ``blobs/sha256/``.

    Mirrors what a containerd-image-store daemon (or ``buildx --output type=oci``)
    exports — no legacy ``manifest.json``. ``image_ref`` is recorded on the index
    descriptor's ``io.containerd.image.name`` annotation (omit for an untagged
    export); ``multi_arch`` wraps the image manifest in a nested platform index.
    """
    config: dict[str, object] = {}
    if entrypoint is not None:
        config["Entrypoint"] = entrypoint
    if cmd is not None:
        config["Cmd"] = cmd

    members: dict[str, bytes] = {"oci-layout": json.dumps({"imageLayoutVersion": "1.0.0"}).encode()}

    def _blob(payload: dict[str, object]) -> str:
        data = json.dumps(payload).encode()
        digest = hashlib.sha256(data).hexdigest()
        members[f"blobs/sha256/{digest}"] = data
        return digest

    config_digest = _blob({"config": config})
    manifest_digest = _blob(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": f"sha256:{config_digest}"},
            "layers": [],
        }
    )

    if multi_arch:
        subindex_digest = _blob(
            {
                "schemaVersion": 2,
                "mediaType": "application/vnd.oci.image.index.v1+json",
                "manifests": [
                    {
                        "mediaType": "application/vnd.oci.image.manifest.v1+json",
                        "digest": f"sha256:{manifest_digest}",
                    }
                ],
            }
        )
        top_digest, top_media = subindex_digest, "application/vnd.oci.image.index.v1+json"
    else:
        top_digest, top_media = manifest_digest, "application/vnd.oci.image.manifest.v1+json"

    descriptor: dict[str, object] = {"mediaType": top_media, "digest": f"sha256:{top_digest}"}
    if image_ref is not None:
        descriptor["annotations"] = {"io.containerd.image.name": image_ref}
    members["index.json"] = json.dumps(
        {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json", "manifests": [descriptor]}
    ).encode()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def venv_archive(*, top_dir: str = "ree-venv", command: str | None = None) -> bytes:
    """A gzipped packed-venv tarball with a ``<top_dir>/pyvenv.cfg`` member.

    ``command`` populates the ``command = ...`` line Python records the venv's
    build directory in; omit it to mimic an older venv that lacks one.
    """
    lines = ["home = /usr", "version = 3.11"]
    if command is not None:
        lines.append(f"command = {command}")
    data = ("\n".join(lines) + "\n").encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(f"{top_dir}/pyvenv.cfg")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def not_an_archive() -> bytes:
    return b"this is not a tar archive at all"


class MemoryAccessor:
    """An ``ArtifactAccessor`` backed by an in-memory ``{path: bytes}`` map."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = dict(files or {})

    def stat(self, rel_path: str) -> ArtifactFile:
        data = self.files.get(rel_path)
        if data is None:
            return ArtifactFile()
        return ArtifactFile(
            exists=True,
            is_file=True,
            size=len(data),
            digest="sha256:" + hashlib.sha256(data).hexdigest(),
        )

    def read(self, rel_path: str, *, max_bytes: int) -> bytes | None:
        data = self.files.get(rel_path)
        return data if (data is not None and len(data) <= max_bytes) else None

    def open(self, rel_path: str):
        data = self.files.get(rel_path)
        return io.BytesIO(data) if data is not None else None
