import { execFileSync } from "node:child_process";
import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  dockerBuildScript,
  dockerRunScript,
  EXPERIMENT_OUTPUT_FILE,
  generateSbom,
  main,
  openPort,
  provideHbom,
  provideMetadata,
  provisionWorkbench,
  pythonHelloWorld,
  releaseWorkbench,
  runEvaluate,
  runExperiment,
  sealRee,
  startReeCreation,
  testActivation,
  uploadSource,
} from "./helpers/flow";

/**
 * The golden-path journey: one workbench, one runtime build, every pipeline
 * page exercised in order. Provisioning (bench container + nested dockerd
 * boot) and the cold DinD runtime build are the expensive parts of any e2e
 * test, so the per-page assertions live here as steps of a single run instead
 * of each paying that setup again in a spec of its own. Branches off this
 * path (e.g. the origin-URL source fetch, which locks the source config) keep
 * their own specs.
 *
 * A failing step fails the test and skips the rest — by design: every later
 * page depends on the earlier state anyway, and the step name in the failure
 * pinpoints the stage. The workbench release is the last step; the
 * workbenchCleanup fixture still covers teardown when an earlier step fails.
 */

const PROJECT_DIR = "python_hello_world";
const RUNTIME_PATH = "python_hello_world/runtime.tar";

test.describe("REE pipeline", () => {
  test("golden path: provision through seal and release on one workbench", async ({ page }) => {
    // The whole pipeline in one test: provisioning + a cold DinD build +
    // activation + experiment each carry a 90-180s worst case of their own,
    // so the per-test budget must cover their sum.
    test.setTimeout(12 * 60 * 1000);

    await test.step("provision workbench", async () => {
      await startReeCreation(page);
      await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
      await expect(page.getByRole("button", { name: /Provision workbench/i })).toBeVisible();

      // Asserts the hub canvas appears and the Source page is reachable.
      await provisionWorkbench(page);
    });

    await test.step("upload source tarball", async () => {
      const clearSource = await uploadSource(page, pythonHelloWorld());

      await expect(clearSource).toBeVisible();
      await expect(page.getByText(/Configuration locked/)).toBeVisible();
      // The archive name appears both in the committed Source Snapshot field
      // and as the Name in the Workspace Snapshot metadata, so match the first.
      await expect(
        page.getByText("python-hello-world.tar.gz", { exact: true }).first(),
      ).toBeVisible();

      // Workspace Snapshot surfaces the backend-computed source metadata. An
      // uploaded tarball reports "Upload" as its origin and a known byte size.
      const snapshot = page.getByRole("region", { name: "Workspace Snapshot" });
      await expect(snapshot.getByText("Origin", { exact: true })).toBeVisible();
      await expect(snapshot.getByText("Upload", { exact: true })).toBeVisible();
      await expect(snapshot.getByText("Size", { exact: true })).toBeVisible();
      await expect(snapshot.getByText("python-hello-world.tar.gz", { exact: true })).toBeVisible();
    });

    await test.step("browse uploaded files in the workspace tree", async () => {
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Expand files" }).click();
      await expect(page.getByRole("button", { name: "Collapse files" })).toBeVisible();

      const archiveNodeNames = [
        ...new Set(
          execFileSync("tar", ["-tzf", pythonHelloWorld()], { encoding: "utf8" })
            .split("\n")
            .map((entry) => entry.trim())
            .filter(Boolean)
            .map((entry) => entry.replace(/\/+$/, "").split("/").filter(Boolean).pop())
            .filter((name): name is string => Boolean(name)),
        ),
      ];
      await page.getByPlaceholder("Filter files…").fill("workspace");
      for (const nodeName of archiveNodeNames) {
        const escaped = nodeName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        await expect(page.getByRole("button", { name: new RegExp(escaped) })).toBeVisible();
      }
      await page.getByRole("button", { name: "Collapse files" }).click();
    });

    await test.step("provide metadata", async () => {
      await provideMetadata(page, {
        name: "ree-hello-world",
        version: "1.0.0",
        description: "A reusable execution environment for the Python hello world archive.",
      });

      await expect(page.getByPlaceholder("deepfold-protein-structure-prediction")).toHaveValue(
        "ree-hello-world",
      );
      await expect(page.getByPlaceholder("1.0.0")).toHaveValue("1.0.0");
      await expect(page.getByPlaceholder("REE for reproducible execution of...")).toHaveValue(
        "A reusable execution environment for the Python hello world archive.",
      );
    });

    await test.step("run evaluation", async () => {
      await runEvaluate(page);
      await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible();
    });

    await test.step("build runtime", async () => {
      await buildRuntime(page, dockerBuildScript(PROJECT_DIR, RUNTIME_PATH), RUNTIME_PATH);

      // buildRuntime leaves the Build page docked; re-open the Build node to
      // confirm the build persisted as a completed (re-buildable) run.
      await openPort(page, "Build");
      await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible();
    });

    await test.step("provide hardware BOM", async () => {
      await provideHbom(page, "Intel Core i9-14900K");
      await expect(main(page).getByPlaceholder("Intel Core i9-14900K").first()).toHaveValue(
        "Intel Core i9-14900K",
      );
    });

    await test.step("generate SBOM", async () => {
      await generateSbom(page);
      await expect(
        page
          .getByRole("region", { name: "Generate SBOM" })
          .getByText("SBOM ready", { exact: true })
          .first(),
      ).toBeVisible();
    });

    await test.step("test activation", async () => {
      await testActivation(
        page,
        dockerRunScript("python -c \"import pandas; print('activation ok')\"", RUNTIME_PATH),
      );
      await expect(main(page).getByRole("button", { name: /Re-run/ })).toBeVisible();
    });

    await test.step("run experiment", async () => {
      // Asserts the run reaches "pass" and renders the verify script check row.
      await runExperiment(page, {
        name: "python-hello",
        runScript: dockerRunScript(
          "python python_hello_world/main.py",
          RUNTIME_PATH,
          EXPERIMENT_OUTPUT_FILE,
        ),
        expectedStdout: "Pandas Hello World",
      });
    });

    await test.step("seal and download the REE", async () => {
      await sealRee(page);

      const downloadButton = page.getByRole("banner").getByRole("button", { name: /Download REE/ });
      await expect(downloadButton).toBeEnabled();
      const [download] = await Promise.all([page.waitForEvent("download"), downloadButton.click()]);
      expect(download.suggestedFilename()).toMatch(/\.zip$/i);

      // The experiment opted its result into the seal, so the bundle carries the
      // author baseline. Zip stores entry names as plaintext, so the raw bytes
      // reveal the entry without unpacking.
      const stream = await download.createReadStream();
      const chunks: Buffer[] = [];
      for await (const chunk of stream) chunks.push(chunk as Buffer);
      expect(Buffer.concat(chunks).includes("ree/results/python-hello/result.txt")).toBe(true);
    });

    await test.step("release workbench", async () => {
      // Asserts the return to the landing view; the workbenchCleanup fixture
      // then sees a released session and no-ops.
      await releaseWorkbench(page);
    });
  });
});
