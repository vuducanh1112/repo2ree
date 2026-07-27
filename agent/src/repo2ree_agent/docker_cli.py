"""Low-level Docker CLI subprocess adapter.

This module owns process I/O and timeout mechanics. ``DockerRuntime`` retains
lifecycle policy, naming, injection, and protocol-frame interpretation.
"""

from __future__ import annotations

import os
import selectors
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import suppress

from repo2ree_agent.workbench_runtime import WorkbenchGoneError
from repo2ree_protocol.agent import COPY_CHUNK_BYTES

CONTAINER_GONE_EXIT_CODES = frozenset({126, 137})
FAILURE_OUTPUT_TAIL_BYTES = 16 * 1024


def failure_detail(stderr: str, stdout: str) -> str:
    return stderr.strip() or stdout.strip()


def tail_text(output: bytes) -> str:
    return output[-FAILURE_OUTPUT_TAIL_BYTES:].decode(errors="replace").strip()


def stream_exec(cmd: list[str], timeout: int, what: str) -> Iterator[bytes]:
    """Yield stdout chunks while bounding silence rather than total duration."""
    deadline = time.monotonic() + timeout
    stdout_tail = bytearray()
    completed = False
    with tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr)
        if proc.stdout is None:
            raise RuntimeError("Popen stdout pipe unavailable")
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        try:
            stdout_open = True
            while stdout_open:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _kill_process(proc)
                    raise subprocess.TimeoutExpired(cmd, timeout)
                events = selector.select(timeout=min(remaining, 0.1))
                if not events:
                    continue
                for _key, _mask in events:
                    chunk = os.read(proc.stdout.fileno(), COPY_CHUNK_BYTES)
                    if not chunk:
                        stdout_open = False
                        break
                    _append_tail(stdout_tail, chunk)
                    yield chunk
                    deadline = time.monotonic() + timeout
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill_process(proc)
                raise subprocess.TimeoutExpired(cmd, timeout)
            returncode = proc.wait(timeout=remaining)
            completed = True
        except subprocess.TimeoutExpired:
            _kill_process(proc)
            raise
        finally:
            selector.close()
            proc.stdout.close()
            if not completed and proc.poll() is None:
                _kill_process(proc)
        if returncode != 0:
            stderr.seek(0)
            detail = tail_text(stderr.read()) or tail_text(bytes(stdout_tail)) or "(no output on stdout/stderr)"
            message = f"{what} failed (exit {returncode}): {detail}"
            if returncode in CONTAINER_GONE_EXIT_CODES or "No such container" in detail:
                raise WorkbenchGoneError(message)
            raise RuntimeError(message)


def docker_out(args: tuple[str, ...], timeout: int) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed: {failure_detail(result.stderr, result.stdout)}")
    return result.stdout.strip()


def image_present(image: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=30).returncode == 0


def _append_tail(tail: bytearray, chunk: bytes) -> None:
    tail.extend(chunk)
    if len(tail) > FAILURE_OUTPUT_TAIL_BYTES:
        del tail[: len(tail) - FAILURE_OUTPUT_TAIL_BYTES]


def _kill_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.kill()
    with suppress(Exception):
        proc.wait(timeout=5)
