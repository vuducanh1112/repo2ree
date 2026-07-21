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
so it runs under a bare ``python3`` shebang regardless of what execs it. It is
the pure-API mirror of the frontend golden path (``ree-pipeline.spec.ts``): the
same journey — one workbench, one runtime build, every pipeline stage exercised
in order — driven only through the public surface:

    createRee -> observeRun (provision)
      -> listReeSteps (discover the authoring steps + prerequisites)
      -> listScriptTemplates (discover the reserved script paths)
      -> source:upload-init / uploadSourceBytes / source:upload-complete
      -> observeRun (extract)
      -> getReeState -> writeReeFile / readReeFile
      -> patchReeIntent (metadata)
      -> startEvaluate -> observeRun -> getEvaluateReport
      -> writeReeFile (build script) -> startBuild -> observeRun
      -> patchReeIntent (declare runtime artifact + hardware BOM)
      -> startSbomGeneration -> observeRun -> startSbomCrossCheck -> observeRun
      -> writeReeFile (activation script) -> startActivationTest -> observeRun
      -> patchReeIntent (declare experiment) -> writeReeFile (run + verify)
         -> startExperiment -> observeRun
      -> getReeState (ree_steps overlay) -> getScorecard
      -> sealRee -> downloadReeArchive -> deleteRee

The build, activation, and experiment stages drive a real cold Docker-in-Docker
runtime build (pandas on ``python:3.11-slim``) inside the workbench — the same
work the frontend golden path does, so the recording shows the genuine cost of
authoring a reproducible environment, not a stub.
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


# ------------------------------------------------------------------
# The project being authored, and the REE recipe scripts that turn it into a
# reproducible environment. Kept byte-for-byte in step with the frontend golden
# path's ``python_hello_world`` fixture so both e2e mirrors build the same
# runtime and assert the same "Pandas Hello World" evidence.
# ------------------------------------------------------------------

# The archive extracts under this top-level directory; the runtime tarball the
# build produces lands beside the sources.
PROJECT_DIR = "python_hello_world"
RUNTIME_PATH = f"{PROJECT_DIR}/runtime.tar"

# REE-owned recipe scripts live under a reserved overlay: a fresh REE seeds the
# build and activation slots, and naming an experiment settles its own reserved
# run-script path. Authoring a stage means writing its script to the reserved
# path, then declaring the intent. The paths themselves are *not* hardcoded here
# — the session discovers them at runtime from listScriptTemplates (see chapter
# 2), the way an agent driving cold from the OpenAPI would. The experiment name
# is kept deliberately slug-safe (no whitespace) so it substitutes directly into
# the catalog's ``{slug}`` path pattern without needing core's slug rules.
EXPERIMENT_NAME = "python-hello"
# Workspace file the experiment run script tees its stdout into; the verify
# script reads it back and its exit code is the verdict.
EXPERIMENT_OUTPUT_FILE = "result.txt"

# The built image's tag, shared by build/activation/experiment scripts.
_IMAGE = "pandas-hello:latest"

_DOCKERFILE = """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
"""

_MAIN_PY = """\
import pandas as pd


def main():
    data = {"Greeting": ["Hello", "Hi", "Hey"], "Target": ["World", "Pandas", "Docker"]}
    df = pd.DataFrame(data)
    print("--- Pandas Hello World ---")
    print(df)


if __name__ == "__main__":
    main()
"""

# Build the runtime image from the project and save it as the runtime tarball.
BUILD_SCRIPT = f"""\
#!/usr/bin/env sh
set -eu
docker build -t {_IMAGE} {PROJECT_DIR}
docker save {_IMAGE} -o {RUNTIME_PATH}
"""


def _docker_run_script(command: str, *, capture: str | None = None) -> str:
    """A self-contained runnable script: load the built runtime if absent, then
    enter it with its own ``docker run``, bind-mounting the workspace so declared
    file outputs surface. Mirrors the frontend helper of the same shape."""
    tee = f' | tee "{capture}"' if capture else ""
    return f"""\
#!/usr/bin/env sh
set -eu
if ! docker image inspect {_IMAGE} >/dev/null 2>&1; then
  docker load < "{RUNTIME_PATH}"
fi
docker run --rm -v "$(pwd):/workspace" -w /workspace {_IMAGE} {command}{tee}
"""


# Activation proves the built runtime is inhabitable — import the installed dep.
ACTIVATION_SCRIPT = _docker_run_script("python -c \"import pandas; print('activation ok')\"")

# The experiment runs the project and captures its stdout as the author baseline.
EXPERIMENT_RUN_SCRIPT = _docker_run_script(f"python {PROJECT_DIR}/main.py", capture=EXPERIMENT_OUTPUT_FILE)

# The verify script owns the claim: the captured stdout contains the expected line.
EXPERIMENT_VERIFY_SCRIPT = f"""\
#!/usr/bin/env sh
set -eu
grep -Fq "Pandas Hello World" "{EXPERIMENT_OUTPUT_FILE}"
"""


def make_source_archive() -> bytes:
    """The ``python_hello_world`` project as an in-memory .tar.gz — a Dockerfile,
    a pandas requirement, and a script whose output the experiment verifies."""
    files = {
        f"{PROJECT_DIR}/Dockerfile": _DOCKERFILE.encode(),
        f"{PROJECT_DIR}/requirements.txt": b"pandas==2.2.1\n",
        f"{PROJECT_DIR}/main.py": _MAIN_PY.encode(),
    }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def put_file(ree_id: str, path: str, content: str) -> None:
    """Author a workspace file (writeReeFile). Used for the REE recipe scripts —
    the build, activation, and experiment scripts live in the workspace and are
    referenced by path from the typed intent."""
    call("PUT", f"/api/v1/rees/{ree_id}/files/content", {"path": path, "content": content})


def run_stage(ree_id: str, method: str, path: str, payload: dict, *, what: str) -> dict:
    """Kick off a background pipeline run and block on observeRun until it settles,
    asserting success. Returns the run's start response. This is the automation
    idiom every heavyweight stage (evaluate, build, sbom, activation, experiment)
    shares: POST to start, long-poll to await."""
    started = call(method, path, payload)
    run_id = started["run_id"]
    status = wait_for_run(ree_id, run_id)
    check(status == "succeeded", f"{what} did not succeed (settled {status})")
    return started


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

    chapter("2. Discover the authoring model")
    note("listReeSteps publishes the authoring steps, their order, and their prerequisites")
    steps_catalog = call("GET", "/api/v1/ree-steps")
    step_keys = [step["key"] for step in steps_catalog["steps"]]
    check("build" in step_keys and "seal" in step_keys, "step catalog missing core steps")
    # The catalog is the DAG as data: `requires` names each step's prerequisites,
    # `actions` the operationIds that advance it — enough to plan a traversal
    # without hardcoding the pipeline shape.
    sbom_step = next(step for step in steps_catalog["steps"] if step["key"] == "sbom")
    check(sbom_step["requires"] == ["build"], "sbom should require build")
    ok(f"{len(step_keys)} authoring steps discovered: {' → '.join(step_keys)}")

    note("listScriptTemplates publishes where each REE-owned script belongs — no hardcoded paths")
    catalog = call("GET", "/api/v1/script-templates")
    build_script_path = catalog["build"]["path"]
    activation_script_path = catalog["activation"]["run_script_path"]
    experiment_run_script_path = catalog["experiment"]["run_script_path_pattern"].replace("{slug}", EXPERIMENT_NAME)
    experiment_verify_script_path = catalog["experiment"]["verify_script_path_pattern"].replace(
        "{slug}", EXPERIMENT_NAME
    )
    check(build_script_path and activation_script_path, "catalog did not resolve the reserved paths")
    ok(f"reserved paths resolved (build → {build_script_path})")

    chapter("3. Upload a source archive")
    archive = make_source_archive()
    archive_name = "python-hello-world.tar.gz"
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

    chapter("4. Inspect the compact state")
    note("getReeState returns durable state + file metadata, never inline contents")
    state = call("GET", f"/api/v1/rees/{ree_id}/state")
    check(
        f"{PROJECT_DIR}/Dockerfile" in {f["path"] for f in state.get("files", [])},
        "extracted Dockerfile not visible in state",
    )
    ok("workspace tree reflects the uploaded project")

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
    ok("metadata recorded")

    chapter("6. Evaluate reproducibility readiness")
    note("scans the sources for dependency signals; the report backs the SBOM cross-check")
    run_stage(ree_id, "POST", f"/api/v1/rees/{ree_id}/evaluate", {}, what="evaluate")
    report = call("GET", f"/api/v1/rees/{ree_id}/evaluate/report")
    check(isinstance(report, dict) and report, "evaluate produced no report")
    ok("reproducibility report generated")

    chapter("7. Build the runtime")
    note("author the reserved build script, then run it — a real cold docker build in the workbench")
    put_file(ree_id, build_script_path, BUILD_SCRIPT)
    note("read the reserved script back (readReeFile returns octet-stream, not JSON)")
    rc, out, err = _run_curl([f"{BASE_URL}/api/v1/rees/{ree_id}/files/raw?path={build_script_path}"])
    check(rc == 0 and out.decode() == BUILD_SCRIPT, f"build script did not round-trip: {_curl_detail(rc, err)}")
    run_stage(ree_id, "POST", f"/api/v1/rees/{ree_id}/build-runtime", {}, what="build")
    built = call("GET", f"/api/v1/rees/{ree_id}/state")
    check(RUNTIME_PATH in {f["path"] for f in built.get("files", [])}, "runtime tarball not produced")
    ok(f"runtime image built and saved to {RUNTIME_PATH}")

    chapter("8. Declare the runtime artifact and hardware BOM")
    note("bind the produced tarball as the runtime, and record the machine it was built on")
    declared = call(
        "PATCH",
        f"/api/v1/rees/{ree_id}/intent",
        {
            "ree_intent_patch": {
                "runtime": RUNTIME_PATH,
                "hardware_description": {"cpus": {"Intel Core i9-14900K": {"vendor": "Intel", "cores_per_cpu": 24}}},
            }
        },
    )
    check(declared["ree_intent"]["runtime"] == RUNTIME_PATH, "runtime artifact not declared")
    check(
        "Intel Core i9-14900K" in declared["ree_intent"]["hardware_description"]["cpus"],
        "hardware BOM entry not recorded",
    )
    ok("runtime artifact and hardware BOM declared")

    chapter("9. Generate and cross-check the SBOM")
    note("scan the runtime tarball for its software bill of materials")
    run_stage(
        ree_id,
        "POST",
        f"/api/v1/rees/{ree_id}/generate-sbom",
        {"produced_runtime_path": RUNTIME_PATH},
        what="SBOM generation",
    )
    note("join the SBOM against the evaluate report — do the declared deps appear in the runtime?")
    run_stage(ree_id, "POST", f"/api/v1/rees/{ree_id}/cross-check-sbom", {}, what="SBOM cross-check")
    ok("SBOM generated and cross-checked against the scanned dependencies")

    chapter("10. Prove activation")
    note("activation is the required run that proves the built runtime is inhabitable")
    put_file(ree_id, activation_script_path, ACTIVATION_SCRIPT)
    run_stage(ree_id, "POST", f"/api/v1/rees/{ree_id}/activation-test", {}, what="activation")
    ok("runtime activates: pandas imports inside the sealed image")

    chapter("11. Run an experiment")
    note("declare a named experiment; naming it settles its reserved run-script path")
    experiment_declared = call(
        "PATCH",
        f"/api/v1/rees/{ree_id}/intent",
        {
            "ree_intent_patch": {
                "experiments": [
                    {
                        "name": EXPERIMENT_NAME,
                        "verify_script": experiment_verify_script_path,
                        "output_paths": [EXPERIMENT_OUTPUT_FILE],
                    }
                ]
            }
        },
    )
    settled_run_script = experiment_declared["ree_intent"]["experiments"][0]["run_script"]
    check(
        settled_run_script == experiment_run_script_path,
        "experiment run-script path did not settle to the discovered pattern",
    )
    note("author the run script (captures stdout) and the verify script (owns the claim)")
    put_file(ree_id, experiment_run_script_path, EXPERIMENT_RUN_SCRIPT)
    put_file(ree_id, experiment_verify_script_path, EXPERIMENT_VERIFY_SCRIPT)
    run_stage(
        ree_id,
        "POST",
        f"/api/v1/rees/{ree_id}/experiments/{EXPERIMENT_NAME}:run",
        {},
        what="experiment",
    )
    ok(f"experiment {EXPERIMENT_NAME!r} passed — declared validation held")

    chapter("12. Review the authoring steps")
    note("getReeState carries a ree_steps overlay: done / ready / blocked per step")
    state = call("GET", f"/api/v1/rees/{ree_id}/state")
    status_by_step = {step["key"]: step["status"] for step in state["ree_steps"]}
    print("    " + "  ".join(f"{key}={status}" for key, status in status_by_step.items()))
    # Every run-backed step now reads done; only the seal remains — ready, since
    # sealing is the next (and last) action.
    for step_key in ("source", "build", "sbom", "crosscheck", "activation", "experiments"):
        check(status_by_step[step_key] == "done", f"step {step_key} should be done, was {status_by_step[step_key]}")
    check(status_by_step["seal"] == "ready", "seal should be the remaining ready step")
    ok("every authoring step is done — only the seal remains")

    chapter("13. Read the reproducibility scorecard")
    note("the scorecard aggregates intent + receipts into an ordinal reproducibility level")
    scorecard = call("GET", f"/api/v1/rees/{ree_id}/scorecard")
    check("level" in scorecard, "scorecard missing its level")
    ok(f"reproducibility level {scorecard['level_code']} — {scorecard['level_name']}")

    chapter("14. Seal and download")
    note("seal binds the whole record; package the source and the experiment baselines")
    sealed = call(
        "POST",
        f"/api/v1/rees/{ree_id}/ree:seal",
        {"include_source": True, "include_results": True},
    )
    seal_hash = sealed["ree_session"]["seal_hash"]
    check(seal_hash.startswith("sha256:"), "seal did not produce a sha256 hash")
    ok(f"sealed as {seal_hash}")
    with tempfile.TemporaryDirectory() as work:
        rc, _, err = _run_curl(["-o", "ree.zip", f"{BASE_URL}/api/v1/rees/{ree_id}/ree-archive"], cwd=work)
        check(rc == 0, f"archive download failed: {_curl_detail(rc, err)}")
        data = (Path(work) / "ree.zip").read_bytes()
    entries = zipfile.ZipFile(io.BytesIO(data)).namelist()
    check(len(entries) > 0, "sealed archive is empty")
    # The experiment declared an output, so its baseline rides along in the bundle
    # — the same evidence the frontend golden path asserts on its downloaded zip.
    result_entry = f"ree/results/{EXPERIMENT_NAME}/{EXPERIMENT_OUTPUT_FILE}"
    check(result_entry in entries, f"experiment baseline {result_entry} missing from the bundle")
    ok(f"downloaded sealed archive: {len(entries)} entries, {len(data)} bytes")

    chapter("15. Tear down")
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
