"""Run the showcases through the command line: each test runs `ree` on the machine its showcase names."""

from __future__ import annotations

from repo2ree_testbed.runs.api_showcase import main

if __name__ == "__main__":
    raise SystemExit(main("cli"))
