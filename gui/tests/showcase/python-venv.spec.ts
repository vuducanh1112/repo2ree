import { expect, test } from "../helpers/fixtures";
import {
  activateExperimentEnvironment,
  buildExperimentEnvironment,
  commandScript,
  EXPERIMENT_OUTPUT_FILE,
  generateScript,
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
  uploadSource,
} from "../helpers/flow";

const PROJECT_DIR = "source";
const EXPERIMENT_ENVIRONMENT_PATH = `${PROJECT_DIR}/runtime-venv.tar.gz`;

const VENV_DIR = "/tmp/ree-venv";

const buildExperimentEnvironmentScript = `#!/usr/bin/env sh
set -eu

EXPERIMENT_ENVIRONMENT_FILE=${JSON.stringify(EXPERIMENT_ENVIRONMENT_PATH)}
VENV_DIR=${JSON.stringify(VENV_DIR)}

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --no-cache-dir -r ${PROJECT_DIR}/requirements.txt
tar -czf "$EXPERIMENT_ENVIRONMENT_FILE" -C "$(dirname "$VENV_DIR")" "$(basename "$VENV_DIR")"
`;

test.describe("REE pip pipeline", () => {
  test("docker-less workbench: pip venv as the experiment environment artifact", async ({
    page,
  }) => {
    await test.step("provision a python:slim workbench", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page);
    });

    await test.step("upload source tarball", async () => {
      const clearSource = await uploadSource(page, pythonPipHelloWorld());
      await expect(clearSource).toBeVisible();
      await expect(page.getByText("python-venv.tar.gz", { exact: true }).first()).toBeVisible();
    });

    await test.step("run evaluation", async () => {
      await runEvaluate(page);
    });

    await test.step("generate a build script from the repository", async () => {
      await openPort(page, "Build Experiment Environment");
      await expect(
        main(page).getByRole("heading", { name: "Build Experiment Environment", exact: true }),
      ).toBeVisible();

      const { message, graph } = await generateScript(page);
      expect(message).toMatch(/Loaded a generated build script/);
      expect(graph).toContain("build-experiment-environment-inference");
      expect(graph).toContain("root-pip-requirements-v1");

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
      await openPort(page, "Build Experiment Environment");
      const { graph, script } = await generateScript(page, /Generate from experiment environment/);
      expect(graph).toContain("activate-experiment-environment-inference");
      expect(script).toMatch(/tar -xzf/);
      expect(script).toMatch(new RegExp(`VENV_DIR=${VENV_DIR}`));
      expect(script).toMatch(/exec "\$@"/);
      await saveActivateScript(page, script);
    });

    await test.step("test activation", async () => {
      await activateExperimentEnvironment(page);
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
