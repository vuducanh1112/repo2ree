import { readFileSync } from "node:fs";
import { expect, test } from "../helpers/fixtures";
import {
  buildRuntime,
  generateScript,
  INSTANT_RUNTIME_PATH,
  instantHelloWorld,
  instantRecipe,
  keepReeArchive,
  LIGHTWEIGHT_WORKBENCH_IMAGE,
  main,
  openPort,
  provisionWorkbench,
  releaseWorkbench,
  runEvaluate,
  runExperiment,
  sealRee,
  startReeCreation,
  testActivation,
  uploadSource,
} from "../helpers/flow";

/**
 * The authoring golden path on the instant project: every stage from an empty
 * bench to a sealed, downloaded REE, on a bench without a Docker daemon and
 * with nothing to download. Each step leaves a before/after screenshot for
 * inspection; the run's behaviour recording is checked separately.
 */
test.describe("Instant authoring", () => {
  test("authors, seals and downloads the instant project", async ({ page }) => {
    await test.step("provision a bench without a Docker daemon", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page, { imageRef: LIGHTWEIGHT_WORKBENCH_IMAGE });
    });

    await test.step("upload the project", async () => {
      await uploadSource(page, instantHelloWorld());
      await expect(
        page.getByText("instant-hello-world.tar.gz", { exact: true }).first(),
      ).toBeVisible();
    });

    await test.step("evaluate", async () => {
      await runEvaluate(page);
    });

    await test.step("inference proposes a venv build", async () => {
      await openPort(page, "Build");
      const { message, graph } = await generateScript(page);
      expect(message).toMatch(/Loaded a generated build script/);
      expect(graph).toContain("root-pip-requirements-v1");
      await expect(page.getByLabel("Build script")).toContainText(/python -m venv/);
      await expect(main(page)).not.toContainText(/docker build/);
    });

    await test.step("build the runtime", async () => {
      await buildRuntime(page, instantRecipe("build_script.sh"), INSTANT_RUNTIME_PATH);
    });

    await test.step("test activation", async () => {
      await testActivation(page, instantRecipe("activation.sh"));
    });

    await test.step("run the experiment", async () => {
      await runExperiment(page, {
        name: "instant-hello",
        runScript: instantRecipe("experiment.sh"),
        expectedStdout: "Hello, World!",
      });
    });

    await test.step("seal and download", async () => {
      await sealRee(page);
      const archive = readFileSync(await keepReeArchive(page));
      expect(archive.includes("ree/results/instant-hello/result.txt")).toBe(true);
    });

    await test.step("release the workbench", async () => {
      await releaseWorkbench(page);
    });
  });
});
