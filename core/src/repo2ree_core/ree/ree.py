from pathlib import Path

from pydantic import BaseModel


class ReproducibleExecutionEnvironment(BaseModel):
    name: str

    runtime: Path | None

    sbom: Path

    hardware_description: dict

    build_runtime_script: Path

    validate_runtime_reproducibility_script: Path


class ReproducibleExecutionEnvironment_2(BaseModel):
    name: str
    version: str
    description: str | None

    source_repository: str
    commit: str

    runtime: Path | None
    build_runtime_script: Path

    sbom: Path

    hardware_description: dict

    entrypoint: str

    validate_runtime_reproducibility_script: Path
