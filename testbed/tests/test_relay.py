"""A relay between a store's workbench and the API: it carries bytes until a fault cuts it."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator

import pytest

from repo2ree_testbed.stack.relay import Relay


@pytest.fixture
def echo() -> Iterator[int]:
    server = socket.create_server(("127.0.0.1", 0))

    def serve() -> None:
        while True:
            try:
                connection, _ = server.accept()
            except OSError:
                return
            threading.Thread(
                target=lambda c=connection: [c.sendall(d) for d in iter(lambda: c.recv(1024), b"")], daemon=True
            ).start()

    threading.Thread(target=serve, daemon=True).start()
    yield int(server.getsockname()[1])
    server.close()


def test_a_relay_carries_bytes_both_ways(echo: int) -> None:
    relay = Relay("127.0.0.1", echo)
    with socket.create_connection(("127.0.0.1", relay.port), timeout=5) as client:
        client.sendall(b"ping")
        assert client.recv(4) == b"ping"
    relay.close()


def test_a_partition_holds_what_is_in_flight_without_closing_and_healing_delivers_it(echo: int) -> None:
    relay = Relay("127.0.0.1", echo)
    with socket.create_connection(("127.0.0.1", relay.port), timeout=5) as client:
        client.sendall(b"before")
        assert client.recv(6) == b"before"

        relay.partition()
        client.sendall(b"during")
        client.settimeout(0.3)
        with pytest.raises(TimeoutError):
            client.recv(6)  # Nothing arrives, and nothing closes: a network that stopped delivering.

        relay.heal()
        client.settimeout(5)
        assert client.recv(6) == b"during"
    relay.close()
