"""Private Docker payload carried inside an opaque ``WorkbenchRef`` token."""

from __future__ import annotations

import base64
import binascii
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from repo2ree_protocol.agent import WorkbenchRef


class DockerWorkbenchHandle(BaseModel):
    """Docker's self-contained workbench address; never crosses the wire directly."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    ree_id: str
    container_name: str
    volume_name: str
    exec_path: str = "repo2ree-exec"


def encode_reference(handle: DockerWorkbenchHandle) -> WorkbenchRef:
    payload = base64.urlsafe_b64encode(handle.model_dump_json().encode()).rstrip(b"=").decode()
    return WorkbenchRef(runtime="docker", token=payload)


def decode_reference(ref: WorkbenchRef) -> DockerWorkbenchHandle:
    if ref.runtime != "docker":
        raise ValueError(f"Docker runtime cannot handle {ref.runtime!r} workbench reference")
    try:
        padding = "=" * (-len(ref.token) % 4)
        raw = base64.b64decode(ref.token + padding, altchars=b"-_", validate=True)
        return DockerWorkbenchHandle.model_validate_json(raw)
    except (binascii.Error, UnicodeDecodeError, ValidationError) as exc:
        raise ValueError("invalid Docker workbench reference") from exc
