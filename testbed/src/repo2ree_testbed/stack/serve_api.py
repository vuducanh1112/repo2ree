"""Run the E2E API on an OS-assigned, already-reserved host port."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m repo2ree_testbed.stack.serve_api <port-file>")

    port_file = Path(sys.argv[1])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", 0))  # noqa: S104 - test stack; reachable from workbench containers by design
        listener.listen()
        listener.set_inheritable(True)

        port = listener.getsockname()[1]
        port_file.write_text(f"{port}\n", encoding="ascii")
        uvicorn.run("repo2ree_api.main:app", fd=listener.fileno(), log_level="info")


if __name__ == "__main__":
    main()
