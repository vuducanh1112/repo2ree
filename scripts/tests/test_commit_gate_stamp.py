import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
TOOL = ROOT / "scripts/publish/commit_gate_stamp.py"


def test_commit_gate_stamp_round_trip_uses_temporary_index(tmp_path: Path) -> None:
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

    subprocess.run([sys.executable, TOOL, "write"], check=True, env=environment)
    subprocess.run([sys.executable, TOOL, "verify"], check=True, env=environment)

    stamp = tmp_path / ".validation-certificates/commit-gate-ok"
    assert stamp.read_text() == "test-tree\n"
    index_entries = [line.split("|", 1)[1] for line in log.read_text().splitlines() if line.startswith("add -A|")]
    assert len(index_entries) == 1
    assert index_entries[0]
    assert not Path(index_entries[0]).exists()
