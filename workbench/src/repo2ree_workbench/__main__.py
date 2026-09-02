"""Run the workbench service."""

from __future__ import annotations

import sys

from repo2ree_workbench.app import main

if __name__ == "__main__":
    main(sys.argv[1:])
