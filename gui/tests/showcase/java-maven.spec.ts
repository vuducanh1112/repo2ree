import { expect, test } from "../helpers/fixtures";
import {
  buildRuntime,
  dockerBuildScript,
  dockerRunScript,
  EXPERIMENT_OUTPUT_FILE,
  generateScript,
  openPort,
  packedProject,
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
 * Another language and toolchain through the same lifecycle: a Maven project
 * whose Dockerfile builds it on a Temurin JDK (pinned by digest) and resolves
 * its one dependency, org.json, from Maven Central. The build is the project's
 * own `docker build` on the bench's daemon; the runtime is the saved image.
 */

const PROJECT_DIR = "java_hello_world";
const RUNTIME_PATH = `${PROJECT_DIR}/runtime.tar`;
const IMAGE = "java-hello";
const CLASSPATH = "'/app/target/classes:/app/target/dependency/*'";

test.describe("Java with Maven", () => {
  test("a Maven project is built, run, sealed and released", async ({ page }) => {
    await test.step("provision the lab's default bench", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page);
    });

    await test.step("upload the project", async () => {
      await uploadSource(page, packedProject(PROJECT_DIR));
      await expect(
        page.getByText("java-hello-world.tar.gz", { exact: true }).first(),
      ).toBeVisible();
    });

    await test.step("evaluate", async () => {
      await runEvaluate(page);
    });

    await test.step("inference proposes the project's own docker build", async () => {
      await openPort(page, "Build");
      const { message, graph } = await generateScript(page);
      expect(message).toMatch(/Loaded a generated build script/);
      expect(graph).toContain("single-project-root-dockerfile-v1");
      await expect(page.getByLabel("Build script")).toContainText(/docker build/);
    });

    await test.step("build the runtime: Maven compiles and fetches org.json", async () => {
      await buildRuntime(page, dockerBuildScript(PROJECT_DIR, RUNTIME_PATH, IMAGE), RUNTIME_PATH);
    });

    await test.step("test activation: the JVM starts", async () => {
      await testActivation(page, dockerRunScript("java -version", RUNTIME_PATH, undefined, IMAGE));
    });

    await test.step("run the experiment", async () => {
      await runExperiment(page, {
        name: "java-hello",
        runScript: dockerRunScript(
          `java -cp ${CLASSPATH} com.example.Main`,
          RUNTIME_PATH,
          EXPERIMENT_OUTPUT_FILE,
          IMAGE,
        ),
        expectedStdout: '"greeting": "Hello"',
      });
    });

    await test.step("seal the REE", async () => {
      await sealRee(page);
    });

    await test.step("release the workbench", async () => {
      await releaseWorkbench(page);
    });
  });
});
