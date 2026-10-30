import { readFileSync } from "node:fs";
import { expect, test } from "../helpers/fixtures";
import {
  buildRuntime,
  generateScript,
  INSTANT_DOCKER_RUNTIME_PATH,
  instantDockerHelloWorld,
  instantRecipe,
  keepReeArchive,
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

const PROJECT = "instant_docker_hello_world";

/**
 * The authoring golden path on the product's default bench, one with its own
 * Docker daemon: the build is a real `docker build` on that daemon, the runtime
 * a saved image, activation and the experiment `docker run`s of it. The image is
 * built FROM scratch, so nothing is pulled or downloaded and every stage still
 * takes seconds.
 */
test.describe("Instant Docker authoring", () => {
  test("authors, seals and downloads the instant Docker project on a dind bench", async ({
    page,
  }) => {
    await test.step("provision the lab's default bench", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page);
    });

    await test.step("upload the project", async () => {
      await uploadSource(page, instantDockerHelloWorld());
      await expect(
        page.getByText("instant-docker-hello-world.tar.gz", { exact: true }).first(),
      ).toBeVisible();
    });

    await test.step("evaluate", async () => {
      await runEvaluate(page);
    });

    await test.step("inference proposes a docker build", async () => {
      await openPort(page, "Build");
      const { message, graph } = await generateScript(page);
      expect(message).toMatch(/Loaded a generated build script/);
      expect(graph).toContain("single-project-root-dockerfile-v1");
      await expect(page.getByLabel("Build script")).toContainText(/docker build/);
    });

    await test.step("build the image on the bench's own daemon", async () => {
      // The recipe adds the bench's busybox to the build context, which an
      // image FROM scratch needs and inference cannot know.
      await buildRuntime(
        page,
        instantRecipe("build_script.sh", PROJECT),
        INSTANT_DOCKER_RUNTIME_PATH,
      );
      await expect(main(page)).toContainText(/docker build/);
    });

    await test.step("test activation", async () => {
      await testActivation(page, instantRecipe("activation.sh", PROJECT));
    });

    await test.step("run the experiment", async () => {
      await runExperiment(page, {
        name: "instant-docker-hello",
        runScript: instantRecipe("experiment.sh", PROJECT),
        expectedStdout: "Hello, World!",
      });
    });

    await test.step("seal and download", async () => {
      await sealRee(page);
      const archive = readFileSync(await keepReeArchive(page));
      expect(archive.includes("ree/results/instant-docker-hello/result.txt")).toBe(true);
    });

    await test.step("release the workbench", async () => {
      await releaseWorkbench(page);
    });
  });
});
