import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  EXPERIMENT_OUTPUT_FILE,
  provisionWorkbench,
  pythonPipHelloWorld,
  releaseWorkbench,
  runEvaluate,
  runExperiment,
  sealRee,
  startReeCreation,
  testActivation,
  uploadSource,
} from "./helpers/flow";

/**
 * The docker-less branch of the pipeline: the workbench base image *is* the
 * runtime environment. A plain python:slim bench (picked via the "Custom…"
 * image option) has no nested dockerd — the agent injects the executor and
 * base tools, warns about the missing docker substrate, and provisions anyway.
 * The build step is then just `pip install` into a venv, packed as the runtime
 * artifact, and every runnable restores that venv instead of `docker load`-ing
 * an image.
 *
 * python:slim's default command (an interactive `python3`) exits immediately
 * when detached, so this also exercises the agent's pause-command fallback
 * that keeps such benches alive.
 *
 * Kept lean on purpose: metadata/HBOM/SBOM pages are covered by the golden
 * path; this spec only walks the stages the pip flow actually changes.
 */

const WORKBENCH_IMAGE = "docker.io/library/python:3.11-slim";
const PROJECT_DIR = "python_pip_hello_world";
const RUNTIME_PATH = "runtime-venv.tar.gz";

// Where the live venv lives inside the bench. Deliberately OUTSIDE the
// workspace: the workspace is snapshot-hashed on every intent PATCH, and a
// ~7k-file venv in it slows each PATCH to ~25s — enough to time out the run
// and release steps. Only the packed tarball (one workspace file) is tracked,
// mirroring how the docker flow keeps its live image in /var/lib/docker.
// A venv bakes absolute paths, so it must be restored to where it was built.
const VENV_DIR = "/tmp/ree-venv";

// Build: create the environment with pip alone and pack it as the runtime
// artifact (a single workspace file the Build page's artifact picker selects).
const buildScript = `#!/usr/bin/env sh
set -eu

RUNTIME_FILE=${JSON.stringify(RUNTIME_PATH)}
VENV_DIR=${JSON.stringify(VENV_DIR)}

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --no-cache-dir -r ${PROJECT_DIR}/requirements.txt
tar -czf "$RUNTIME_FILE" -C "$(dirname "$VENV_DIR")" "$(basename "$VENV_DIR")"
`;

/**
 * A self-contained run script for the pip flow. Mirrors the docker variant's
 * contract — restore the runtime artifact if it isn't already in place, then
 * run the command inside it — but "load the runtime" here means unpacking the
 * venv (outside the workspace, see VENV_DIR) rather than `docker load`-ing an
 * image.
 */
function venvRunScript(command: string, outputFile?: string): string {
  const capture = outputFile ? ` | tee ${JSON.stringify(outputFile)}` : "";
  return `#!/usr/bin/env sh
set -eu

RUNTIME_FILE=${JSON.stringify(RUNTIME_PATH)}
VENV_DIR=${JSON.stringify(VENV_DIR)}

if [ ! -x "$VENV_DIR/bin/python" ]; then
  tar -xzf "$RUNTIME_FILE" -C "$(dirname "$VENV_DIR")"
fi

"$VENV_DIR/bin/"${command}${capture}
`;
}

test.describe("REE pip pipeline", () => {
  test("docker-less workbench: pip venv as the runtime artifact", async ({ page }) => {
    // Provisioning pulls python:slim cold and the build pip-installs pandas
    // over the network; both are the dominant costs here.
    test.setTimeout(10 * 60 * 1000);

    await test.step("provision a python:slim workbench", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page, { imageRef: WORKBENCH_IMAGE });
    });

    await test.step("upload source tarball", async () => {
      const clearSource = await uploadSource(page, pythonPipHelloWorld());
      await expect(clearSource).toBeVisible();
      await expect(
        page.getByText("python-pip-hello-world.tar.gz", { exact: true }).first(),
      ).toBeVisible();
    });

    await test.step("run evaluation", async () => {
      // requirements.txt is the only dependency manifest — no Dockerfile.
      await runEvaluate(page);
    });

    await test.step("build runtime via pip", async () => {
      await buildRuntime(page, buildScript, RUNTIME_PATH);
    });

    await test.step("test activation", async () => {
      await testActivation(
        page,
        venvRunScript("python -c \"import pandas; print('activation ok')\""),
      );
    });

    await test.step("run experiment", async () => {
      await runExperiment(page, {
        name: "python-pip-hello",
        runScript: venvRunScript(`python ${PROJECT_DIR}/main.py`, EXPERIMENT_OUTPUT_FILE),
        expectedStdout: "Pandas Hello World",
      });
    });

    await test.step("seal the REE", async () => {
      await sealRee(page);
      await expect(
        page.getByRole("banner").getByRole("button", { name: /Download REE/ }),
      ).toBeEnabled();
    });

    await test.step("release workbench", async () => {
      await releaseWorkbench(page);
    });
  });
});
