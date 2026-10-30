import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
RECEIPT_TOOL = ["-m", "scripts.gates.publish_gate"]
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
elif [[ "$1" == "version" ]]; then
    printf '%s\n' "${FAKE_PLATFORM:-linux/amd64}"
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
    receipt = tmp_path / ".receipts/publish-gate.json"

    subprocess.run(
        [sys.executable, *RECEIPT_TOOL, "write", receipt, "revision-1"],
        check=True,
        env=environment,
        cwd=ROOT,
    )
    subprocess.run(
        [sys.executable, *RECEIPT_TOOL, "verify", receipt, "revision-1"],
        check=True,
        env=environment,
        cwd=ROOT,
    )

    environment["FAKE_IMAGE_ID"] = CHANGED_IMAGE_ID
    changed = subprocess.run(
        [sys.executable, *RECEIPT_TOOL, "verify", receipt, "revision-1"],
        check=False,
        env=environment,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert changed.returncode == 1
    assert "changed after publish-gate" in changed.stderr


def test_a_receipt_names_its_platform_and_holds_only_on_a_daemon_of_that_platform(tmp_path: Path) -> None:
    environment = _fake_environment(tmp_path)
    directory = tmp_path / ".receipts"
    receipt = subprocess.run(
        [sys.executable, *RECEIPT_TOOL, "path", directory],
        check=True,
        env=environment,
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert receipt == str(directory / "publish-gate-linux-amd64.json")

    subprocess.run(
        [sys.executable, *RECEIPT_TOOL, "write", receipt, "revision-1"], check=True, env=environment, cwd=ROOT
    )
    assert json.loads(Path(receipt).read_text())["platform"] == "linux/amd64"

    environment["FAKE_PLATFORM"] = "linux/arm64"
    elsewhere = subprocess.run(
        [sys.executable, *RECEIPT_TOOL, "verify", receipt, "revision-1"],
        check=False,
        env=environment,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert elsewhere.returncode == 1
    assert "certifies linux/amd64 images; this daemon holds linux/arm64" in elsewhere.stderr
