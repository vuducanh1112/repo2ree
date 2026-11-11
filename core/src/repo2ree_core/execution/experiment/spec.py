"""Minimal executable view of an activation or experiment definition."""

from __future__ import annotations

from dataclasses import dataclass

from repo2ree_ree.paths import validate_relative_path


@dataclass(frozen=True)
class RunnableSpec:
    """A script run inside the activation, or with no run script the activation alone."""

    activate_script: str
    run_script: str = ""
    verify_script: str = ""
    output_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.run_script:
            validate_relative_path(self.run_script)
        elif self.verify_script or self.output_paths:
            raise ValueError("the activation alone has no verify script and no outputs")
        validate_relative_path(self.activate_script)
        if self.verify_script:
            validate_relative_path(self.verify_script)
        for path in self.output_paths:
            validate_relative_path(path)
