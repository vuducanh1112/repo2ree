import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
TOOL = ["-m", "scripts.gates.commit_gate"]


def test_commit_gate_receipt_round_trip_uses_temporary_index(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "git.log"
    git = bin_dir / "git"
    git.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s|%s\\n" "$*" "${GIT_INDEX_FILE:-}" >> "$GIT_LOG"\n'
        'case "$1 $2" in\n'
        f"  'rev-parse --show-toplevel') echo {tmp_path} ;;\n"
        "  'write-tree ') echo test-tree ;;\n"
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    git.chmod(0o755)
    environment = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "GIT_LOG": str(log)}

    subprocess.run([sys.executable, *TOOL, "write"], check=True, env=environment, cwd=ROOT)
    subprocess.run([sys.executable, *TOOL, "verify"], check=True, env=environment, cwd=ROOT)

    receipt = json.loads((tmp_path / ".receipts/commit-gate.json").read_text())
    assert (receipt["gate"], receipt["revision"], receipt["tree"]) == ("commit-gate", None, "test-tree")
    index_entries = [line.split("|", 1)[1] for line in log.read_text().splitlines() if line.startswith("add -A|")]
    assert len(index_entries) == 1
    assert index_entries[0]
    assert not Path(index_entries[0]).exists()
