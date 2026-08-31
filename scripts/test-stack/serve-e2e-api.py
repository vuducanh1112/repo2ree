"""Run the E2E API on an OS-assigned, already-reserved loopback port."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    """Publish the reserved port, then serve Uvicorn through that socket."""
    if len(sys.argv) != 2:
        raise SystemExit("usage: serve-e2e-api.py <port-file>")

    port_file = Path(sys.argv[1])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.set_inheritable(True)

        port = listener.getsockname()[1]
        port_file.write_text(f"{port}\n", encoding="ascii")
        uvicorn.run("repo2ree_api.main:app", fd=listener.fileno(), log_level="info")


if __name__ == "__main__":
    main()
