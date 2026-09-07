import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
RECEIPT_TOOL = ROOT / "scripts/publish/publish-gate-receipt.sh"
PUSH_TOOL = ROOT / "scripts/publish/push-image-set.sh"
IMAGE_ID = "sha256:" + "1" * 64
CHANGED_IMAGE_ID = "sha256:" + "2" * 64


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


def _fake_environment(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "git",
        """#!/usr/bin/env bash
case "$1" in
check-ignore) exit 0 ;;
write-tree) echo test-tree ;;
*) exit 2 ;;
esac
""",
    )
    _write_executable(
        bin_dir / "docker",
        """#!/usr/bin/env bash
if [[ "$1 $2" == "image inspect" ]]; then
    printf '%s\n' "$FAKE_IMAGE_ID"
else
    printf '%s\n' "$*" >>"$DOCKER_LOG"
fi
""",
    )
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "FAKE_IMAGE_ID": IMAGE_ID,
        "DOCKER_LOG": str(tmp_path / "docker.log"),
    }


def test_receipt_binds_revision_tree_and_local_image_ids(tmp_path: Path) -> None:
    environment = _fake_environment(tmp_path)
    receipt = tmp_path / ".validation-certificates/publish-gate-ok"

    subprocess.run(
        [RECEIPT_TOOL, "write", receipt, "revision-1"],
        check=True,
        env=environment,
    )
    subprocess.run(
        [RECEIPT_TOOL, "verify", receipt, "revision-1"],
        check=True,
        env=environment,
    )

    environment["FAKE_IMAGE_ID"] = CHANGED_IMAGE_ID
    changed = subprocess.run(
        [RECEIPT_TOOL, "verify", receipt, "revision-1"],
        check=False,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert changed.returncode == 1
    assert "changed after publish-gate" in changed.stderr


def test_push_uses_certified_ids_instead_of_mutable_local_tags(tmp_path: Path) -> None:
    environment = _fake_environment(tmp_path)
    environment["REGISTRIES"] = "registry.example/team"
    receipt = tmp_path / "publish-gate-ok"
    receipt.write_text(
        "revision\trevision-1\n"
        "tree\ttest-tree\n"
        + "".join(
            f"image\t{name}\t{IMAGE_ID}\n"
            for name in (
                "repo2ree-gui",
                "repo2ree-backend",
                "repo2ree-provider-docker",
            )
        )
    )

    subprocess.run(
        [PUSH_TOOL, "revision-1", receipt],
        check=True,
        env=environment,
    )

    calls = Path(environment["DOCKER_LOG"]).read_text().splitlines()
    tag_calls = calls[::2]
    assert len(tag_calls) == 3
    assert all(call.startswith(f"tag {IMAGE_ID} ") for call in tag_calls)
    assert all(":local" not in call for call in tag_calls)
