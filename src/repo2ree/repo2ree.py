from datetime import datetime
from pathlib import Path


from repo2ree.ree.ree import ReproducibleExecutionEnvironment
from repo2ree.create_dockerfile import generate_dockerfile_and_build_image
from repo2ree.sbom.generate_sbom import generate_sbom


def repo2ree(repo_path: Path, output_dir: Path) -> ReproducibleExecutionEnvironment:
    ##############
    assert repo_path.exists(), "Repository path must exist."
    assert output_dir.exists(), "Output directory must exist."
    ##############

    docker_image_path = generate_dockerfile_and_build_image(
        repo_path, datetime(2025, 10, 1), output_dir
    )
    # dockerfile = output_dir / "Dockerfile-ree"

    sbom_path = generate_sbom(output_dir / "ree.tar", output_dir)

    validate_runtime_reproducibility_script_contents = ""
    validate_runtime_reproducibility_script_contents += "#!/bin/bash\n"
    validate_runtime_reproducibility_script_contents += (
        "echo 'Validating runtime reproducibility...'\n"
    )
    validate_runtime_reproducibility_script_contents += (
        f"docker load -i {docker_image_path}\n"
    )
    validate_runtime_reproducibility_script_contents += (
        f"docker run --rm {docker_image_path}\n"
    )

    validate_runtime_reproducibility_script = (
        output_dir / "validate_runtime_reproducibility.sh"
    )
    validate_runtime_reproducibility_script.write_text(
        validate_runtime_reproducibility_script_contents
    )

    ree = ReproducibleExecutionEnvironment(
        name="example",
        runtime=docker_image_path,
        sbom=sbom_path,
        hardware_description={"cpu": "x86_64", "memory": "16GB"},
        build_runtime_script=Path("/path/to/build/script"),
        validate_runtime_reproducibility_script=validate_runtime_reproducibility_script,
    )

    ree_file = output_dir / "ree.json"
    ree_file.write_text(ree.model_dump_json(indent=2))

    return ree
