import { expect, test } from "../helpers/fixtures";
import {
  buildExperimentEnvironment,
  commandScript,
  EXPERIMENT_OUTPUT_FILE,
  generateScript,
  LIGHTWEIGHT_WORKBENCH_IMAGE,
  main,
  openPort,
  provisionWorkbench,
  pythonPipHelloWorld,
  releaseWorkbench,
  runEvaluate,
  runExperiment,
  saveActivateScript,
  sealRee,
  startReeCreation,
  testActivation,
  uploadSource,
} from "../helpers/flow";

/**
 * The docker-less branch of the pipeline: the workbench base image *is* the
 * runtime environment. The test supplies a plain python:slim with no nested
 * dockerd through the provider's custom image input, so this works whether or
 * not that image is also curated in the lab's catalog. The lab injects the
 * executor and base tools and provisions against it. The build step is then
 * just `pip install` into a venv, packed as the runtime artifact, and every
 * runnable restores that venv instead of `docker load`-ing an image.
 *
 * python:slim's default command (an interactive `python3`) exits immediately
 * when detached, so this also exercises the lab's pause-command fallback
 * that keeps such benches alive.
 *
 * Kept lean on purpose: metadata/HBOM/SBOM pages are covered by the golden
 * path; this spec only walks the stages the pip flow actually changes.
 */

const PROJECT_DIR = "source";
// Packed inside the project dir, not at the workspace root: the declared runtime
// must live within the logical project root, or script inference refuses to
// resolve a runtime contract for it (experiment_environment_outside_project_root).
const EXPERIMENT_ENVIRONMENT_PATH = `${PROJECT_DIR}/runtime-venv.tar.gz`;

// Where the live venv lives inside the bench. Deliberately OUTSIDE the
// workspace: the workspace is snapshot-hashed on every intent PATCH, and a
// ~7k-file venv in it slows each PATCH to ~25s — enough to time out the run
// and release steps. Only the packed tarball (one workspace file) is tracked,
// mirroring how the docker flow keeps its live image in /var/lib/docker.
// A venv bakes absolute paths, so it must be restored to where it was built.
const VENV_DIR = "/tmp/ree-venv";

// Build: create the environment with pip alone and pack it as the runtime
// artifact (a single workspace file the Build page's artifact picker selects).
const buildExperimentEnvironmentScript = `#!/usr/bin/env sh
set -eu

EXPERIMENT_ENVIRONMENT_FILE=${JSON.stringify(EXPERIMENT_ENVIRONMENT_PATH)}
VENV_DIR=${JSON.stringify(VENV_DIR)}

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --no-cache-dir -r ${PROJECT_DIR}/requirements.txt
tar -czf "$EXPERIMENT_ENVIRONMENT_FILE" -C "$(dirname "$VENV_DIR")" "$(basename "$VENV_DIR")"
`;

/**
 * A self-contained run script for the pip flow. Mirrors the docker variant's
 * contract — restore the runtime artifact if it isn't already in place, then
 * run the command inside it — but "load the experiment environment" here means unpacking the
 * venv (outside the workspace, see VENV_DIR) rather than `docker load`-ing an
 * image.
 */
test.describe("REE pip pipeline", () => {
  test("docker-less workbench: pip venv as the experiment environment artifact", async ({
    page,
  }) => {
    await test.step("provision a python:slim workbench", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page, { imageRef: LIGHTWEIGHT_WORKBENCH_IMAGE });
    });

    await test.step("upload source tarball", async () => {
      const clearSource = await uploadSource(page, pythonPipHelloWorld());
      await expect(clearSource).toBeVisible();
      await expect(page.getByText("python-venv.tar.gz", { exact: true }).first()).toBeVisible();
    });

    await test.step("run evaluation", async () => {
      // requirements.txt is the only dependency manifest — no Dockerfile.
      await runEvaluate(page);
    });

    await test.step("generate a build script from the repository", async () => {
      // The docker-less inference branch: no Dockerfile, so the only viable
      // strategy is pip-into-a-venv packed as the runtime artifact.
      await openPort(page, "Build Experiment Environment");
      await expect(
        main(page).getByRole("heading", { name: "Build Experiment Environment", exact: true }),
      ).toBeVisible();

      const { message, graph } = await generateScript(page);
      expect(message).toMatch(/Loaded a generated build script/);
      expect(graph).toContain("build-experiment-environment-inference");
      expect(graph).toContain("root-pip-requirements-v1");

      // A venv build, not a container one — the pip renderer, not the docker one.
      await expect(page.getByLabel("Build experiment environment script")).toContainText(
        /python -m venv/,
      );
      await expect(page.getByLabel("Build experiment environment script")).not.toContainText(
        /docker build/,
      );
    });

    await test.step("build experiment environment via pip", async () => {
      await buildExperimentEnvironment(
        page,
        buildExperimentEnvironmentScript,
        EXPERIMENT_ENVIRONMENT_PATH,
      );
    });

    await test.step("generate the activate experiment environment script from the packed venv", async () => {
      // The declared artifact is a real packed venv, so inspection classifies it as a venv
      // experiment environment: restore it and run the given command with it on the path. The
      // venv records its own build directory, so the restore path is recovered, not assumed.
      await openPort(page, "Build Experiment Environment");
      const { graph, script } = await generateScript(page, /Generate from experiment environment/);
      expect(graph).toContain("activate-experiment-environment-inference");
      expect(script).toMatch(/tar -xzf/);
      expect(script).toMatch(new RegExp(`VENV_DIR=${VENV_DIR}`));
      expect(script).toMatch(/exec "\$@"/);
      await saveActivateScript(page, script);
    });

    await test.step("test activation", async () => {
      await testActivation(page);
    });

    await test.step("run experiment", async () => {
      await runExperiment(page, {
        name: "python-pip-hello",
        runScript: commandScript(`python ${PROJECT_DIR}/main.py`, EXPERIMENT_OUTPUT_FILE),
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
