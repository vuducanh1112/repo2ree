from pathlib import Path
import tempfile
import json

from repo2ree_core.dockerfile_utils.build_image import build_docker_image
from repo2ree_core.dockerfile_utils.extract_files import extract_file_from_image


def generate_sbom(runtime_path: Path, output_dir: Path) -> Path:
    ##############
    assert runtime_path.exists(), "Runtime path must exist."
    assert output_dir.exists(), "Output directory must exist."
    ##############

    syft_image_name = "ghcr.io/anchore/syft:v1.36.0"
    # syft_image_digest = (
    #    "sha256:788d70164a2aa4cab235bc6f92956438050bceb8f04a27b9fe6f820469470216"
    # )

    dockerfile_contents = ""
    # dockerfile_contents += f"FROM {syft_image_name}@{syft_image_digest}\n"
    dockerfile_contents += f"FROM {syft_image_name}\n"
    dockerfile_contents += "WORKDIR /workdir\n"
    dockerfile_contents += f"COPY {runtime_path.name} /workdir/{runtime_path.name}\n"
    dockerfile_contents += f'RUN ["/syft", "docker-archive:/workdir/{runtime_path.name}", "-o", "json=/workdir/sbom.json"]'

    with tempfile.TemporaryDirectory() as tmpdir:
        dockerfile_path = Path(tmpdir) / "Dockerfile-syft"
        dockerfile_path.write_text(dockerfile_contents)
        image = build_docker_image(runtime_path.parent, dockerfile_path)

    if image is None:
        raise RuntimeError("Failed to build Syft Docker image for SBOM generation.")

    extract_file_from_image(
        image.id, "/workdir/sbom.json", str(output_dir / "sbom.json")
    )

    image.remove(force=True)

    generated_sbom_path = output_dir / "sbom.json"
    sbom_data = generated_sbom_path.read_text()
    with open(output_dir / "sbom_readable.json", "w") as f:
        parsed = json.loads(sbom_data)
        json.dump(parsed, f, indent=2)

    ##############
    assert generated_sbom_path.exists(), "Generated SBOM file was not created."
    ##############

    return generated_sbom_path


if __name__ == "__main__":
    generate_sbom(
        Path("./foo_test/outputs/requirements_txt_test/ree.tar"),
        Path("./foo_test/outputs/requirements_txt_test"),
    )
