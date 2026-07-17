#!/usr/bin/env python3
"""Author a REE end to end over the HTTP API — a real terminal session, no frontend.

This is the pure-API counterpart of ``frontend/tests/e2e``: it drives the public,
automation-ready API through its whole authoring lifecycle. It is deliberately an
*honest* recording — a real terminal session, not a staged one:

  * Every API interaction is a genuine ``curl`` subprocess. The command printed to
    the transcript is the exact one executed (one argv, printed and run), so the
    recording never shows a command that differs from what actually ran.
  * There is no fabricated "agent thinking". The narrative is carried by neutral
    section banners — the author's chapter headings — not by first-person prose
    pretending to be a model's inner monologue.

The Python is pure orchestration: control flow, the observeRun poll loop, JSON
parsing, and assertions. It doubles as a CI check — every response is asserted, so
a broken contract fails the run (and thus the recording). Run it through the stack
orchestrator, which brings a live backend + workbench agent up, points
``API_BASE_URL`` at it, tears it down, and (with ``make e2e-api``) records the
terminal:

    scripts/e2e-stack.sh --script api/tests/e2e/api_agent_walkthrough.py
    make e2e-api            # the same, always recorded to a .cast

Needs only ``curl`` (already required by the orchestrator) and the Python stdlib,
so it runs under a bare ``python3`` shebang regardless of what execs it. Drives
only the public surface:

    createRee -> observeRun (provision)
      -> source:upload-init / uploadSourceBytes / source:upload-complete
      -> observeRun (extract)
      -> getReeState -> writeReeFile / readReeFile
      -> patchReeIntent -> sealRee -> downloadReeArchive -> deleteRee
"""

from __future__ import annotations

import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# Terminal statuses a background run settles into (mirrors run_registry).
TERMINAL = {"succeeded", "failed", "canceled"}

# ------------------------------------------------------------------
# Presentation — honest editorial structure, no simulated agent voice
# ------------------------------------------------------------------


def chapter(title: str) -> None:
    """A section banner: the author's chapter heading, not agent narration."""
    print(f"\n\033[1m━━ {title} " + "━" * max(0, 56 - len(title)) + "\033[0m")


def note(msg: str) -> None:
    """A dim author aside explaining a non-obvious step."""
    print(f"\033[2m# {msg}\033[0m")


def ok(msg: str) -> None:
    print(f"\033[32m  ✓ {msg}\033[0m")


class WalkthroughError(RuntimeError):
    """A failed assertion or unexpected response — ends the session non-zero."""


def check(condition: object, msg: str) -> None:
    if not condition:
        raise WalkthroughError(msg)


# ------------------------------------------------------------------
# HTTP — every call is a single real curl. The command printed IS the command
# executed: one argv, echoed and run. Python only orchestrates and parses.
# ------------------------------------------------------------------


def _run_curl(argv: list[str], *, cwd: str | None = None, echo: bool = True) -> tuple[int, bytes, bytes]:
    """Run one curl command and return (returncode, stdout, stderr).

    ``-sS`` silences the progress meter but keeps transport errors; ``--fail-with-body``
    turns an HTTP >= 400 into a non-zero exit while still emitting the response body,
    so pass/fail comes from curl's own exit code — no ``-w`` status plumbing to hide —
    and the error envelope still reaches the transcript. The printed line is exactly
    what runs; binary file args are relative names resolved against ``cwd`` so the
    shown command stays clean *and* faithful."""
    argv = ["curl", "-sS", "--fail-with-body", *argv]
    if echo:
        print(f"\033[1;34m$ {shlex.join(argv)}\033[0m")
    proc = subprocess.run(argv, capture_output=True, cwd=cwd)  # noqa: S603,S607 — curl is a required stack dep
    return proc.returncode, proc.stdout, proc.stderr


def _curl_detail(rc: int, err: bytes) -> str:
    return err.decode(errors="replace").strip() or f"HTTP error (curl exit {rc}; see response above)"


def call(method: str, path: str, payload: dict | None = None) -> dict:
    """A JSON request as a real curl. Prints the exact command and the parsed
    response (the error envelope too, on failure), then fails the session on any
    transport error or HTTP >= 400."""
    argv = ["-X", method, f"{BASE_URL}{path}"]
    if payload is not None:
        argv += ["-H", "Content-Type: application/json", "--data", json.dumps(payload)]
    rc, out, err = _run_curl(argv)
    try:
        parsed = json.loads(out) if out.strip() else {}
        print(json.dumps(parsed, indent=2))
    except json.JSONDecodeError:
        parsed = {}
        print(out.decode(errors="replace"))
    check(rc == 0, f"{method} {path} failed: {_curl_detail(rc, err)}")
    return parsed


def wait_for_run(ree_id: str, run_id: str) -> str:
    """Tail a background run via the long-polling observeRun endpoint — the
    automation-idiomatic way to await completion — printing each new log line as
    it arrives. Returns the terminal status. The poll curl runs quietly; only the
    streamed log lines reach the transcript."""
    note(f"streaming run {run_id} via observeRun until it settles")
    cursor = 0
    while True:
        url = f"{BASE_URL}/api/v1/rees/{ree_id}/runs/{run_id}/observe?cursor={cursor}&wait_seconds=25"
        # --max-time gives curl headroom past the server-side long-poll window.
        rc, out, err = _run_curl([url, "--max-time", "40"], echo=False)
        check(rc == 0, f"observing run {run_id} failed: {_curl_detail(rc, err)}")
        obs = json.loads(out)
        for entry in obs.get("entries", []):
            print(f"    {entry['stream']}/{entry['level']}: {entry['message']}")
        if obs.get("next_cursor"):
            cursor = int(obs["next_cursor"])
        if obs["run"]["status"] in TERMINAL:
            return obs["run"]["status"]
        time.sleep(0.1)


def make_source_archive() -> bytes:
    """A tiny in-memory .tar.gz standing in for the project being authored."""
    files = {
        "demo-project/README.md": b"# demo project\n",
        "demo-project/requirements.txt": b"requests==2.31.0\n",
        "demo-project/main.py": b"print('hello from the reproduced environment')\n",
    }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


# ==================================================================
# The session
# ==================================================================


def run() -> None:
    print("\033[1mrepo2ree — authoring a REE end to end over the HTTP API\033[0m")
    note(f"every step below is a real curl against {BASE_URL}; nothing is mocked")

    chapter("1. Provision a workbench")
    health = call("GET", "/")
    check(health.get("status") == "online", "service not online")
    created = call("POST", "/api/v1/rees", {"name": "agent-authored-ree"})
    ree_id = created["ree_id"]
    check(ree_id, "no ree_id in create response")
    note(f"provisioning runs in the background as {created['run_id']}")
    check(wait_for_run(ree_id, created["run_id"]) == "succeeded", "provisioning did not succeed")
    ok(f"workbench provisioned for REE {ree_id}")

    chapter("2. Upload a source archive")
    archive = make_source_archive()
    archive_name = "demo-project.tar.gz"
    init = call(
        "POST",
        f"/api/v1/rees/{ree_id}/source:upload-init",
        {"file_name": archive_name, "size": len(archive), "content_type": "application/gzip"},
    )
    token = init["upload_token"]
    note("PUT the raw archive bytes to the returned upload URL")
    with tempfile.TemporaryDirectory() as work:
        (Path(work) / archive_name).write_bytes(archive)
        rc, out, err = _run_curl(
            [
                "-X",
                "PUT",
                f"{BASE_URL}{init['upload_url']}",
                "-H",
                "Content-Type: application/octet-stream",
                "--data-binary",
                f"@{archive_name}",
            ],
            cwd=work,
        )
    stored = json.loads(out) if out.strip() else {}
    print(json.dumps(stored, indent=2))
    check(rc == 0 and stored.get("upload_token") == token, f"upload did not store the token: {_curl_detail(rc, err)}")
    completed = call(
        "POST",
        f"/api/v1/rees/{ree_id}/source:upload-complete",
        {"upload_token": token, "archive_name": archive_name},
    )
    check(wait_for_run(ree_id, completed["run_id"]) == "succeeded", "source extraction did not succeed")
    ok(f"source extracted into the workspace ({len(archive)} bytes)")

    chapter("3. Inspect the compact state")
    note("getReeState returns durable state + file metadata, never inline contents")
    state = call("GET", f"/api/v1/rees/{ree_id}/state")
    check(
        "demo-project/README.md" in {f["path"] for f in state.get("files", [])},
        "extracted README.md not visible in state",
    )
    ok("workspace tree reflects the uploaded project")

    chapter("4. Author a file in the workspace")
    call(
        "PUT",
        f"/api/v1/rees/{ree_id}/files/content",
        {"path": "build.sh", "content": "pip install -r demo-project/requirements.txt\n"},
    )
    note("read the raw bytes back (readReeFile returns octet-stream, not JSON)")
    rc, out, err = _run_curl([f"{BASE_URL}/api/v1/rees/{ree_id}/files/raw?path=build.sh"])
    text = out.decode()
    print(f"    {text}")
    check(rc == 0 and text == "pip install -r demo-project/requirements.txt\n", "round-tripped file mismatch")
    ok("file round-trips byte-for-byte")

    chapter("5. Record authoring intent")
    patched = call(
        "PATCH",
        f"/api/v1/rees/{ree_id}/intent",
        {
            "ree_intent_patch": {
                "name": "agent-authored-ree",
                "catalog_metadata": {
                    "version": "1.0.0",
                    "description": "A REE assembled entirely through the HTTP API.",
                },
            }
        },
    )
    check(patched["ree_intent"]["catalog_metadata"]["version"] == "1.0.0", "intent version not recorded")
    ok("intent recorded")

    chapter("6. Seal and download")
    sealed = call("POST", f"/api/v1/rees/{ree_id}/ree:seal", {"include_source": True})
    seal_hash = sealed["ree_session"]["seal_hash"]
    check(seal_hash.startswith("sha256:"), "seal did not produce a sha256 hash")
    ok(f"sealed as {seal_hash}")
    with tempfile.TemporaryDirectory() as work:
        rc, _, err = _run_curl(["-o", "ree.zip", f"{BASE_URL}/api/v1/rees/{ree_id}/ree-archive"], cwd=work)
        check(rc == 0, f"archive download failed: {_curl_detail(rc, err)}")
        data = (Path(work) / "ree.zip").read_bytes()
    entries = zipfile.ZipFile(io.BytesIO(data)).namelist()
    check(len(entries) > 0, "sealed archive is empty")
    ok(f"downloaded sealed archive: {len(entries)} entries, {len(data)} bytes")

    chapter("7. Tear down")
    deleted = call("DELETE", f"/api/v1/rees/{ree_id}")
    check(deleted.get("state") == "deleted", "delete did not report deleted")
    ok(f"REE {ree_id} deleted")

    print("\n\033[1;32m✓ REE authored, sealed, and torn down — entirely over the HTTP API.\033[0m")


def main() -> int:
    try:
        run()
    except WalkthroughError as exc:
        print(f"\033[31m  ✗ {exc}\033[0m", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
