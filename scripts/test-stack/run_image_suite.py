#!/usr/bin/env python3
"""Run one browser suite or API walkthrough against an owned image stack."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from image_stack import ROOT, ImageStack, Options


def positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("compute locations must be a positive integer")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--compute-locations", type=positive, required=True)
    parser.add_argument("--images", choices=("local", "published"), default="local")
    parser.add_argument("--repository", default="")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()
    if args.images == "local" and (args.repository or args.tag):
        parser.error("--repository and --tag apply only to --images published")
    if args.images == "published" and (not args.repository or not args.tag):
        parser.error("--images published requires --repository and --tag")

    stack = ImageStack(
        Options(
            compute_locations=args.compute_locations,
            image_repository=args.repository if args.images == "published" else "",
            image_tag=args.tag if args.images == "published" else "local",
        )
    )
    status = 0
    started = True
    try:
        stack.up()
        stack.check()
        if args.suite == "demo-api":
            subprocess.run(
                [str(ROOT / "api/tests/e2e/api_walkthrough.py"), "--base-url", stack.api_url], cwd=ROOT, check=True
            )
        else:
            subprocess.run(
                ["npm", "exec", "--", "playwright", "test", "-c", "playwright.config.ts", f"--project={args.suite}"],
                cwd=ROOT / "gui",
                env={**os.environ, "E2E_BASE_URL": stack.gui_url},
                check=True,
            )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        status = 1
    finally:
        if started:
            try:
                stack.down(volumes=True)
            except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
                print(f"stack cleanup failed: {error}", file=sys.stderr)
                status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
