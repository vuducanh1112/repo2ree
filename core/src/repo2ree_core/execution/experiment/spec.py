"""Minimal executable view of an activation test or experiment definition."""

from __future__ import annotations

from dataclasses import dataclass

from repo2ree_core.path_safety import validate_relative_path


@dataclass(frozen=True)
class RunnableSpec:
    run_script: str
    verify_script: str = ""
    output_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_relative_path(self.run_script)
        if self.verify_script:
            validate_relative_path(self.verify_script)
        for path in self.output_paths:
            validate_relative_path(path)
