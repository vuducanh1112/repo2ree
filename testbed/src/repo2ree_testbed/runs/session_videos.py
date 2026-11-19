"""Render CLI tests' terminal sessions to video, beside the runs as their other reports are.

Each CLI test's recording (``<test>/artifacts/cli-session.cast``) becomes ``reports/sessions/<run>/<test>.mp4``:
agg draws it to a GIF and ffmpeg encodes that as H.264. The run itself is never written. A video is rendered again
only when its key changes: the digest of its recording and of how it is rendered (the tools' versions and the
settings), kept beside it as ``<test>.key``. The paths of the videos this call rendered are printed, one a line, for
the recipe to stamp; progress goes to stderr. Videos of runs gone from disk, and of tests their run no longer has,
are removed.

    python -m repo2ree_testbed render-sessions [RUN...] [--jobs N]   # by default, the CLI showcase runs read
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from repo2ree_testbed.artifacts import ROOT, run_dir
from repo2ree_testbed.cli_session import SESSION
from repo2ree_testbed.runs.assess import is_run, target
from repo2ree_testbed.runs.showcase_runs import showcase_runs

SESSIONS = ROOT / "reports" / "sessions"
CAST = SESSION.removesuffix(".ndjson") + ".cast"
AGG = ("--quiet", "--font-size", "12", "--idle-time-limit", "2")
# x264's SVE code dies with an illegal instruction on an aarch64 machine that reports SVE it cannot run (Docker's
# linuxkit VM): there it keeps to NEON.
X264 = ("-x264-params", "asm=NEON") if platform.machine() == "aarch64" else ()
FFMPEG = (
    "-c:v", "libx264", *X264, "-crf", "28", "-tune", "stillimage", "-preset", "slow", "-movflags", "faststart",
    "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
)  # fmt: skip


@dataclass(frozen=True)
class Session:
    """One CLI test's recording, and where its video goes."""

    cast: Path
    video: Path

    @property
    def key_file(self) -> Path:
        return self.video.with_suffix(".key")


class Rendered(BaseModel):
    """What the stamp of a video records: the commit that rendered it, whether the tree differed, and when."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    revision: str
    dirty: bool
    generated: str
    sha256: str


# The recipe that stamps the videos it rendered (just render-cli-sessions), and its stamp file's entries.
STAMPED_BY = "render-cli-sessions"
_STAMPED = TypeAdapter[dict[str, Rendered]](dict[str, Rendered])


def video_of(run: str, test: Path, sessions_dir: Path = SESSIONS) -> Path:
    """Where the video of a run's test, by its directory in the run, goes."""
    return sessions_dir / run / f"{test.name}.mp4"


def rendered_by(video: Path, sessions_dir: Path = SESSIONS) -> Rendered | None:
    """The stamp of a video as it is now, or None where there is no video, or none of this video."""
    if not video.is_file():
        return None
    try:
        stamped = _STAMPED.validate_json((sessions_dir / "stamps" / f"{STAMPED_BY}.json").read_bytes())
    except (OSError, ValidationError):
        return None
    entry = stamped.get(video.relative_to(sessions_dir).as_posix())
    if entry is None or entry.sha256 != hashlib.sha256(video.read_bytes()).hexdigest():
        return None
    return entry


@cache
def renderer() -> str:
    """How a video is rendered: the tools' versions and the settings, so that a change to either renders again."""
    agg = subprocess.run(["agg", "--version"], capture_output=True, text=True, check=True).stdout.strip()
    ffmpeg = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    return "\n".join((agg, ffmpeg, " ".join(AGG), " ".join(FFMPEG)))


def key(session: Session) -> str:
    digest = hashlib.sha256(renderer().encode())
    digest.update(session.cast.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def sessions(run: Path, sessions_dir: Path = SESSIONS) -> list[Session]:
    """The recordings a run's CLI tests left, each with its video's place."""
    return [
        Session(cast, video_of(run.name, cast.parent.parent, sessions_dir))
        for cast in sorted(run.glob(f"tests/*/artifacts/{CAST}"))
    ]


def render(session: Session) -> bool:
    """Render the session's video, unless the one there has its key; whether it rendered."""
    wanted = key(session)
    if session.video.is_file() and session.key_file.is_file() and session.key_file.read_text() == wanted:
        return False
    session.video.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        gif = Path(scratch) / "session.gif"
        subprocess.run(["agg", *AGG, str(session.cast), str(gif)], check=True)
        partial = Path(scratch) / session.video.name
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(gif), *FFMPEG, str(partial)], check=True
        )
        shutil.move(partial, session.video)
    session.key_file.write_text(wanted)
    print(f">> {session.video}", file=sys.stderr)
    return True


def drop_gone(kept: dict[str, list[Session]], sessions_dir: Path = SESSIONS) -> None:
    """Remove the videos of runs gone from disk, and of tests a rendered run no longer has."""
    for folder in sorted(sessions_dir.iterdir()) if sessions_dir.is_dir() else ():
        if not folder.is_dir() or folder.name == "stamps":
            continue
        if folder.name not in kept:
            if not is_run(run_dir() / "e2e" / folder.name):
                shutil.rmtree(folder)
            continue
        wanted = {name for session in kept[folder.name] for name in (session.video.name, session.key_file.name)}
        for path in folder.iterdir():
            if path.name not in wanted:
                path.unlink()


def chosen(given: list[str]) -> list[Path]:
    """The runs named, or by default the CLI showcase runs the overview reads."""
    if given:
        return [target(name) for name in given]
    tiers = showcase_runs(run_dir() / "e2e").tiers
    return [target(str(tier.run)) for tier in tiers if tier.surface == "cli" and tier.run]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*", help="runs, by path or name (default: the CLI showcase runs read)")
    parser.add_argument("--jobs", type=int, default=1, help="videos rendered at once (agg and x264 use several cores)")
    args = parser.parse_args()
    try:
        runs = chosen(args.runs)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    found = {run.name: sessions(run) for run in runs}
    every = [session for each in found.values() for session in each]
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        rendered = [session for session, done in zip(every, pool.map(render, every), strict=True) if done]
    drop_gone(found)
    sys.stdout.write("".join(f"{session.video}\n" for session in rendered))
    print(f">> {len(rendered)} of {len(every)} videos rendered; the rest had their key", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
