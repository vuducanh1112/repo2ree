"""Authored state that does not come from scanning ``upstream``.

Build inference reads only the immutable acquired tree. Activation and
experiment inference additionally depend on state the *author* produced — the
declared runtime path (``ReeIntent.runtime``), experiment declarations, the
*built* runtime artifact in the workspace, and the written build script — which
the design deliberately keeps out of ``RepositoryFacts`` and threads in here as
separate typed dependencies.

The engine stays pure: it never touches the filesystem or ``ReeStore``. It sees
only an ``ArtifactAccessor`` — a narrow read-only view a check can ``stat`` and
(bounded) ``read``. The envelope handler supplies a concrete accessor over
``ReeLayout``; tests supply an in-memory one. The default accessor reports
everything absent, so build inference and pure tests need to pass nothing.
"""

from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.experiment import Experiment


class ArtifactFile(BaseModel):
    """The stat of one workspace-relative path, as inference sees it."""

    model_config = ConfigDict(extra="forbid")

    exists: bool = False
    is_file: bool = False
    size: int = 0
    # ``sha256:<hex>`` of the file's bytes when it is a regular file, else None.
    digest: str | None = None


@runtime_checkable
class ArtifactAccessor(Protocol):
    """Read-only, workspace-relative access to authored bytes.

    Resolves a workspace-relative path against the authored sources (the built
    artifact in the workspace and the written reserved scripts in the overlay).
    ``read`` is bounded: it returns ``None`` for a missing file or one larger
    than ``max_bytes`` so a check can never be forced to load an unbounded
    untrusted artifact into memory.
    """

    def stat(self, rel_path: str) -> ArtifactFile: ...

    def read(self, rel_path: str, *, max_bytes: int) -> bytes | None: ...

    def open(self, rel_path: str) -> BinaryIO | None:
        """A seekable binary stream over the file, or ``None`` if absent.

        Used to inspect a large runtime archive member-by-member without loading
        the whole artifact into memory. The caller closes it.
        """
        ...


class _NullAccessor:
    """Everything absent. The default for build inference and pure tests."""

    def stat(self, rel_path: str) -> ArtifactFile:
        return ArtifactFile()

    def read(self, rel_path: str, *, max_bytes: int) -> bytes | None:
        return None

    def open(self, rel_path: str) -> BinaryIO | None:
        return None


class RuntimeInputs(BaseModel):
    """Authored-state inputs carried on the decision context.

    Immutable like the rest of the context. Holds an ``ArtifactAccessor`` (an
    arbitrary, non-serializable object), so the context is never model-dumped —
    only the report is.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # ``ReeIntent.runtime`` — the declared, workspace-relative runtime artifact
    # path. ``None`` when the author has not declared a runtime.
    declared_runtime_path: str | None = None
    experiments: list[Experiment] = Field(default_factory=list)
    accessor: ArtifactAccessor = Field(default_factory=_NullAccessor)

    def experiment(self, name: str) -> Experiment | None:
        for experiment in self.experiments:
            if experiment.name == name:
                return experiment
        return None
