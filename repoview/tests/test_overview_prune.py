import json
import os
from pathlib import Path

from repo2ree_repoview.overview.bundle import COMMAND
from repo2ree_repoview.overview.prune import prune, stale_overviews


def overview(root: Path, name: str, when: float) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({"command": COMMAND}))
    os.utime(folder, (when, when))
    return folder


def test_the_newest_overviews_stay_and_so_does_the_one_latest_points_to(tmp_path: Path) -> None:
    oldest, old, _newer, _newest = (overview(tmp_path, f"rev{index}", 1000 + index) for index in range(4))
    (tmp_path / "latest").symlink_to(oldest.name)
    # Not an overview: never touched, however old.
    (tmp_path / "notes").mkdir()
    os.utime(tmp_path / "notes", (1, 1))

    assert stale_overviews(tmp_path, keep=2) == [old]
    assert prune(tmp_path, keep=2, dry_run=True) == [old]
    assert old.exists()

    prune(tmp_path, keep=2)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["latest", "notes", "rev0", "rev2", "rev3"]
    assert stale_overviews(tmp_path / "missing") == []
