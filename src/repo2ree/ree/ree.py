from pathlib import Path

from pydantic import BaseModel


class ReproducibleExecutionEnvironment(BaseModel):
    name: str

    runtime: Path | None

    sbom: Path

    hardware_description: dict

    build_runtime_script: Path

    validate_runtime_reproducibility_script: Path
