import tarfile
import click
from pathlib import Path

from repo2ree.cli.cli import cli as repo2ree_cli
from repo2ree.core.ree.ree import ReproducibleExecutionEnvironment


@repo2ree_cli.command()
def create_ree(
    name: str,
    runtime: str,
    sbom: str,
    hardware_description: str,
    build_runtime_script: str,
    validate_runtime_reproducibility_script: str,
):
    if Path(runtime).exists():
        runtime_path = Path(runtime)

    if Path(sbom).exists():
        sbom_path = Path(sbom)

    if Path(build_runtime_script).exists():
        build_runtime_script_path = Path(build_runtime_script)

    if Path(validate_runtime_reproducibility_script).exists():
        validate_runtime_reproducibility_script_path = Path(
            validate_runtime_reproducibility_script
        )

    ree = ReproducibleExecutionEnvironment(
        name=name,
        runtime=runtime_path,
        sbom=sbom_path,
        hardware_description={"cpu": "x86_64", "memory": "16GB"},
        build_runtime_script=build_runtime_script_path,
        validate_runtime_reproducibility_script=validate_runtime_reproducibility_script_path,
    )

    ree_archive_path = Path("./ree.tar.gz")
    with tarfile.open(ree_archive_path, "w:gz") as tar:
        tar.add(runtime_path, arcname=runtime_path.name)
        tar.add(sbom_path, arcname=sbom_path.name)
        tar.add(build_runtime_script_path, arcname=build_runtime_script_path.name)
        tar.add(
            validate_runtime_reproducibility_script_path,
            arcname=validate_runtime_reproducibility_script_path.name,
        )

    click.echo(
        f"Created ree.tar.gz at {ree_archive_path} containing the REE components."
    )
    click.echo(ree.model_dump_json(indent=2))
