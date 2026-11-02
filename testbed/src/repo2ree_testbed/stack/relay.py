"""A TCP relay between a store's workbench and the API, so a fault can cut the network between them.

A partition here behaves as a network that stops delivering, not one that refuses: sockets stay
open, bytes in flight are held, and new connections wait, until the partition heals. That is what a
workbench's pings must notice on their own, and what TCP would deliver late once the network is back.
"""

from __future__ import annotations

import socket
import threading
from contextlib import suppress

_CHUNK = 64 * 1024
_HOLD_POLL_SECONDS = 0.05


class Relay:
    def __init__(self, upstream_host: str, upstream_port: int) -> None:
        self._upstream = (upstream_host, upstream_port)
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._healed = threading.Event()
        self._healed.set()
        self._closed = threading.Event()
        self._sockets: list[socket.socket] = []
        self._lock = threading.Lock()
        threading.Thread(target=self._accept, name="relay-accept", daemon=True).start()

    @property
    def port(self) -> int:
        return int(self._listener.getsockname()[1])

    def partition(self) -> None:
        self._healed.clear()

    def heal(self) -> None:
        self._healed.set()

    def close(self) -> None:
        self._closed.set()
        self._healed.set()
        with suppress(OSError):
            self._listener.close()
        with self._lock:
            for open_socket in self._sockets:
                with suppress(OSError):
                    open_socket.close()

    def _accept(self) -> None:
        while not self._closed.is_set():
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            threading.Thread(target=self._connect, args=(client,), daemon=True).start()

    def _connect(self, client: socket.socket) -> None:
        self._held()  # A connection made while partitioned waits, as its SYN would be retried.
        try:
            upstream = socket.create_connection(self._upstream)
        except OSError:
            client.close()
            return
        with self._lock:
            self._sockets += [client, upstream]
        for source, target in ((client, upstream), (upstream, client)):
            threading.Thread(target=self._pump, args=(source, target), daemon=True).start()

    def _pump(self, source: socket.socket, target: socket.socket) -> None:
        try:
            while data := source.recv(_CHUNK):
                self._held()
                target.sendall(data)
        except OSError:
            pass
        finally:
            for side in (source, target):
                with suppress(OSError):
                    side.shutdown(socket.SHUT_RDWR)

    def _held(self) -> None:
        while not self._healed.wait(_HOLD_POLL_SECONDS):
            if self._closed.is_set():
                return
