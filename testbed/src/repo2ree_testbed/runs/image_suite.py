"""Run one browser suite or the API walkthrough against an image stack."""

from __future__ import annotations

import argparse
import subprocess
import sys

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.runs.e2e import positive
from repo2ree_testbed.stack.clients import GUI, PLAYWRIGHT
from repo2ree_testbed.stack.images import Images, ImageStack
from repo2ree_testbed.stack.process import run


def main() -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed image-suite")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--compute-locations", type=positive, required=True)
    parser.add_argument("--images", choices=("local", "published"), default="local")
    parser.add_argument("--repository", default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--existing", action="store_true")
    args = parser.parse_args()
    if args.existing and args.images != "local":
        parser.error("--existing cannot be combined with --images published")
    if args.images == "local" and (args.repository or args.tag):
        parser.error("--repository and --tag apply only to --images published")
    if args.images == "published" and (not args.repository or not args.tag):
        parser.error("--images published requires --repository and --tag")
    images = Images.tagged(args.repository, args.tag) if args.images == "published" else Images.tagged()
    stack = ImageStack(images, args.compute_locations)
    owned = not args.existing
    status = 0
    try:
        if owned:
            stack.up()
        urls = stack.check()
        if args.suite == "demo-api":
            run([str(ROOT / "api/tests/e2e/api_walkthrough.py"), "--base-url", urls.api])
        else:
            run([*PLAYWRIGHT, f"--project={args.suite}"], cwd=GUI, env={"E2E_BASE_URL": urls.gui})
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        status = 1
    finally:
        if owned:
            try:
                stack.down(volumes=True)
            except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
                print(f"stack cleanup failed: {error}", file=sys.stderr)
                status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
