#!/usr/bin/env python3
"""Author a REE end to end over the HTTP API — a real terminal session, no GUI.

This is the pure-API counterpart of ``gui/tests/e2e``: it drives the public,
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
the pure-API mirror of the GUI golden path (``ree-pipeline.spec.ts``): the
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
      -> generateScriptCandidates (build) -> writeReeFile (build script) -> startBuild -> observeRun
      -> patchReeIntent (declare runtime artifact + hardware BOM)
      -> startSbomGeneration -> observeRun -> startSbomCrossCheck -> observeRun
      -> generateScriptCandidates (activation) -> writeReeFile (activation script) -> startActivationTest -> observeRun
      -> patchReeIntent (declare experiment) -> generateScriptCandidates (experiment)
         -> writeReeFile (run + verify) -> startExperiment -> observeRun
      -> getReeState (ree_steps overlay) -> getScorecard
      -> sealRee -> downloadReeArchive -> deleteRee

The build, activation, and experiment recipe scripts are not hardcoded: each is
inferred from the repository through ``generateScriptCandidates`` and its
decision graph printed, then authored (the build script is complete; the
fail-closed run scaffolds get their one ``set --`` command filled in). Those
stages then drive a real cold Docker-in-Docker runtime build (pandas on
``python:3.11-slim``) inside the workbench — the same work the GUI golden
path does, so the recording shows the genuine cost of authoring a reproducible
environment, not a stub.
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
from typing import Any

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
    proc = subprocess.run(argv, capture_output=True, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


def _curl_detail(rc: int, err: bytes) -> str:
    return err.decode(errors="replace").strip() or f"HTTP error (curl exit {rc}; see response above)"


def call(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
            return str(obs["run"]["status"])
        time.sleep(0.1)


# ------------------------------------------------------------------
# The project being authored, and the REE recipe scripts that turn it into a
# reproducible environment. Kept byte-for-byte in step with the GUI golden
# path's ``python_hello_world`` fixture so both e2e mirrors build the same
# runtime and assert the same "Pandas Hello World" evidence.
# ------------------------------------------------------------------

# The archive extracts under this top-level directory. Where the *build* writes
# the runtime tarball, and the image tag it produces, are no longer hardcoded:
# chapter 7 infers the build script and reads those back out of it — inference
# owns those conventions now, exactly as an author reading the generated script
# would.
PROJECT_DIR = "python_hello_world"

# REE-owned recipe scripts live under a reserved overlay: a fresh REE seeds the
# build and activation slots, and naming an experiment settles its own reserved
# run-script path. Authoring a stage means writing its script to the reserved
# path, then declaring the intent. The paths themselves are *not* hardcoded here
# — the session discovers them at runtime from listScriptTemplates (see chapter
# 2), the way an agent driving cold from the OpenAPI would. The experiment name
# is kept deliberately slug-safe (no whitespace) so it substitutes directly into
# the catalog's ``{slug}`` path pattern without needing core's slug rules.
EXPERIMENT_NAME = "python-hello"
# The inferred experiment scaffold captures stdout to its own ``results/<slug>.log``
# convention (its ``RUN_LOG``); the verify script reads that back and its exit code
# is the verdict. Declared as the experiment's output so the baseline is sealed.
EXPERIMENT_LOG = f"results/{EXPERIMENT_NAME}.log"

# Where the REE keeps its SBOM. Unlike the runtime — which the author's own build
# script writes into the workspace and packaging then lifts — the scan writes
# REE-owned evidence, so it lands in ``artifacts/`` from the start and is
# declared, listed, and bundled at that one path.
SBOM_ARTIFACT_PATH = "artifacts/sbom.json"

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

# Phase 1 inference never selects a run command — it emits a fail-closed scaffold
# with a guarded, empty ``set --``. Authoring an activation or experiment run
# script is therefore: infer the scaffold, then fill in that one line. These are
# the commands the author supplies — activation proves the runtime is inhabitable
# (import the installed dep); the experiment runs the project.
ACTIVATION_COMMAND = "python -c \"import pandas; print('activation ok')\""
EXPERIMENT_COMMAND = f"python {PROJECT_DIR}/main.py"

# The verify script owns the claim: the captured stdout contains the expected
# line. It reads the scaffold's own RUN_LOG (EXPERIMENT_LOG), declared as the
# experiment's output.
EXPERIMENT_VERIFY_SCRIPT = f"""\
#!/usr/bin/env sh
set -eu
grep -Fq "Pandas Hello World" "{EXPERIMENT_LOG}"
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


def run_stage(ree_id: str, method: str, path: str, payload: dict[str, Any], *, what: str) -> dict[str, Any]:
    """Kick off a background pipeline run and block on observeRun until it settles,
    asserting success. Returns the run's start response. This is the automation
    idiom every heavyweight stage (evaluate, build, sbom, activation, experiment)
    shares: POST to start, long-poll to await."""
    started = call(method, path, payload)
    run_id = started["run_id"]
    status = wait_for_run(ree_id, run_id)
    check(status == "succeeded", f"{what} did not succeed (settled {status})")
    return started


# ------------------------------------------------------------------
# Script inference — generate the reserved recipe scripts from the repository
# rather than hardcoding them. Inference is read-only: it proposes candidate
# bytes and the decision graph that produced them, and writes nothing. A chosen
# candidate becomes a script only when the author saves it via writeReeFile.
# ------------------------------------------------------------------


def generate_scripts(ree_id: str, targets: list[dict[str, Any]]) -> dict[str, Any]:
    """Run read-only inference for the requested targets and return the report."""
    return call("POST", f"/api/v1/rees/{ree_id}/script-inferences:generate", {"targets": targets})


def _inference_result(report: dict[str, Any], kind: str, experiment_name: str | None = None) -> dict[str, Any]:
    """The report's result for one target (empty dict if absent)."""
    for result in report.get("results", []):
        target = result.get("target", {})
        if target.get("kind") != kind:
            continue
        if experiment_name is not None and target.get("experiment_name") != experiment_name:
            continue
        return dict(result)
    return {}


def summarize_decision(report: dict[str, Any], kind: str, experiment_name: str | None = None) -> dict[str, Any]:
    """Print the target's decision graph — the executed DAG path and outcome —
    then return its result. This is the same trace the GUI renders; showing
    it proves inference explains itself, whether or not it produced a script."""
    result = _inference_result(report, kind, experiment_name)
    check(bool(result), f"inference returned no result for {kind}")
    decision = result["decision"]
    path = " -> ".join(
        step["node_id"] + (f"[{step['branch']}]" if step.get("branch") else "") for step in decision["steps"]
    )
    print(f"    decision {decision['dag']} v{decision['version']} => {result['status']}")
    print(f"    path: {path}")
    for warning in result.get("warnings", []):
        if warning.get("blocking"):
            print(f"    blocking: {warning['message']}")
    return result


def inferred_script(
    report: dict[str, Any], kind: str, *, rule: str | None = None, experiment_name: str | None = None
) -> str:
    """The body of the target's first non-empty candidate (optionally the one a
    given inference rule produced); empty string when nothing was inferred."""
    result = _inference_result(report, kind, experiment_name)
    for candidate in result.get("candidates", []):
        body = candidate.get("body")
        if not body:
            continue
        if rule is not None and candidate.get("inference_rule") != rule:
            continue
        return str(body)
    return ""


def shell_value(body: str, name: str) -> str:
    """Read a ``NAME=value`` assignment back out of a generated shell script — how
    an author learns where the inferred build writes its runtime, or where the
    experiment scaffold captures its log."""
    for line in body.splitlines():
        if line.startswith(f"{name}="):
            tokens = shlex.split(line[len(name) + 1 :])
            return tokens[0] if tokens else ""
    return ""


def author_command(body: str, command: str) -> str:
    """Fill the scaffold's single guarded, empty ``set --`` line with the run
    command — the one edit Phase 1 deliberately leaves to the author."""
    anchor = "\nset --\n"
    check(body.count(anchor) == 1, "expected exactly one unconfigured 'set --' line in the scaffold")
    return body.replace(anchor, f"\nset -- {command}\n", 1)


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

    chapter("7. Infer and run the build script")
    note("generateScriptCandidates reads the immutable source and proposes the reserved build script — writing nothing")
    build_report = generate_scripts(ree_id, [{"kind": "build"}])
    summarize_decision(build_report, "build")
    # The repo carries both a Dockerfile and a requirements.txt, so inference
    # offers two runtime strategies (a decision, not a default). This REE is a
    # container build — take the Dockerfile candidate.
    build_script = inferred_script(build_report, "build", rule="single-project-root-dockerfile-v1")
    check(build_script, "docker build strategy was not inferred")
    # The generated script owns the runtime-artifact convention; read it back out
    # rather than hardcoding where the build writes.
    runtime_artifact = shell_value(build_script, "RUNTIME_ARTIFACT")
    check(runtime_artifact, "generated build script declares no RUNTIME_ARTIFACT")
    note(f"the inferred build tags its image and saves the runtime tarball to {runtime_artifact}")
    put_file(ree_id, build_script_path, build_script)
    note("read the reserved script back (readReeFile returns octet-stream, not JSON)")
    rc, out, err = _run_curl([f"{BASE_URL}/api/v1/rees/{ree_id}/files/raw?path={build_script_path}"])
    check(rc == 0 and out.decode() == build_script, f"build script did not round-trip: {_curl_detail(rc, err)}")
    run_stage(ree_id, "POST", f"/api/v1/rees/{ree_id}/build-runtime", {}, what="build")
    built = call("GET", f"/api/v1/rees/{ree_id}/state")
    check(runtime_artifact in {f["path"] for f in built.get("files", [])}, "runtime tarball not produced")
    ok(f"runtime image built and saved to {runtime_artifact}")

    chapter("8. Declare the runtime artifact and hardware BOM")
    note("bind the produced tarball as the runtime, and record the machine it was built on")
    declared = call(
        "PATCH",
        f"/api/v1/rees/{ree_id}/intent",
        {
            "ree_intent_patch": {
                "runtime": runtime_artifact,
                "hardware_description": {"cpus": {"Intel Core i9-14900K": {"vendor": "Intel", "cores_per_cpu": 24}}},
            }
        },
    )
    check(declared["ree_intent"]["runtime"] == runtime_artifact, "runtime artifact not declared")
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
        {"produced_runtime_path": runtime_artifact},
        what="SBOM generation",
    )
    # The scan writes REE evidence, not a workspace file: it lands in artifacts/
    # and the intent is patched to that path, so the SBOM shows up in ree_files
    # rather than in the materialized tree the next step's drift check watches.
    scanned = call("GET", f"/api/v1/rees/{ree_id}/state")
    check(
        scanned["ree_intent"]["sbom"] == SBOM_ARTIFACT_PATH,
        f"SBOM should be declared at {SBOM_ARTIFACT_PATH}, was {scanned['ree_intent']['sbom']!r}",
    )
    check(
        SBOM_ARTIFACT_PATH in {file["path"] for file in scanned.get("ree_files", [])},
        f"{SBOM_ARTIFACT_PATH} missing from the REE's own files",
    )
    check(
        "sbom.json" not in {file["path"] for file in scanned.get("files", [])},
        "the SBOM leaked into the materialized workspace",
    )
    ok(f"SBOM written to {SBOM_ARTIFACT_PATH} — REE evidence, outside the workspace")
    note("join the SBOM against the evaluate report — do the declared deps appear in the runtime?")
    run_stage(ree_id, "POST", f"/api/v1/rees/{ree_id}/cross-check-sbom", {}, what="SBOM cross-check")
    ok("SBOM generated and cross-checked against the scanned dependencies")

    chapter("10. Infer the activation scaffold, then author its command")
    note("with the runtime built and declared, inference resolves the runtime contract and emits a scaffold")
    activation_report = generate_scripts(ree_id, [{"kind": "activation_run"}])
    summarize_decision(activation_report, "activation_run")
    activation_scaffold = inferred_script(activation_report, "activation_run")
    check(activation_scaffold, "activation inference produced no scaffold")
    note("Phase 1 never selects the run command; the author fills the guarded 'set --' line and saves")
    activation_script = author_command(activation_scaffold, ACTIVATION_COMMAND)
    put_file(ree_id, activation_script_path, activation_script)
    run_stage(ree_id, "POST", f"/api/v1/rees/{ree_id}/activation-test", {}, what="activation")
    ok("runtime activates: pandas imports inside the sealed image")

    chapter("11. Infer the experiment scaffold, then run it")
    note("declare a named experiment; naming it settles its run-script path, and its declared output is sealed")
    experiment_declared = call(
        "PATCH",
        f"/api/v1/rees/{ree_id}/intent",
        {
            "ree_intent_patch": {
                "experiments": [
                    {
                        "name": EXPERIMENT_NAME,
                        "verify_script": experiment_verify_script_path,
                        "output_paths": [EXPERIMENT_LOG],
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
    note("infer the experiment scaffold (gated on the declaration above), then author its scientific command")
    experiment_report = generate_scripts(ree_id, [{"kind": "experiment_run", "experiment_name": EXPERIMENT_NAME}])
    summarize_decision(experiment_report, "experiment_run", EXPERIMENT_NAME)
    experiment_scaffold = inferred_script(experiment_report, "experiment_run", experiment_name=EXPERIMENT_NAME)
    check(experiment_scaffold, "experiment inference produced no scaffold")
    # The scaffold captures to its own RUN_LOG; it must match the output we
    # declared so the sealed baseline is the file the verify script reads.
    check(
        shell_value(experiment_scaffold, "RUN_LOG") == EXPERIMENT_LOG,
        "experiment scaffold RUN_LOG did not match the declared output",
    )
    experiment_run_script = author_command(experiment_scaffold, EXPERIMENT_COMMAND)
    note("author the run script (its command; capture is inferred) and the verify script (owns the claim)")
    put_file(ree_id, experiment_run_script_path, experiment_run_script)
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
    seal_hash = sealed["ree_state"]["seal_hash"]
    check(seal_hash.startswith("sha256:"), "seal did not produce a sha256 hash")
    ok(f"sealed as {seal_hash}")
    with tempfile.TemporaryDirectory() as work:
        rc, _, err = _run_curl(["-o", "ree.zip", f"{BASE_URL}/api/v1/rees/{ree_id}/ree-archive"], cwd=work)
        check(rc == 0, f"archive download failed: {_curl_detail(rc, err)}")
        data = (Path(work) / "ree.zip").read_bytes()
    entries = zipfile.ZipFile(io.BytesIO(data)).namelist()
    check(len(entries) > 0, "sealed archive is empty")
    # The experiment declared an output, so its baseline rides along in the bundle
    # — the store mirrors the workspace layout, so the inferred results/<slug>.log
    # capture nests under the per-experiment prefix.
    result_entry = f"ree/results/{EXPERIMENT_NAME}/{EXPERIMENT_LOG}"
    check(result_entry in entries, f"experiment baseline {result_entry} missing from the bundle")
    # The SBOM was authored into artifacts/, so packaging carries it verbatim:
    # the same path inside the bundle as on disk, and the same one the manifest
    # declares — nothing to remap, nothing to lift.
    check(f"ree/{SBOM_ARTIFACT_PATH}" in entries, f"ree/{SBOM_ARTIFACT_PATH} missing from the bundle")
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
