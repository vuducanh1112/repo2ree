import { execFileSync } from "node:child_process";
import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  crossCheckSbom,
  dockerBuildScript,
  dockerRunScript,
  EXPERIMENT_OUTPUT_FILE,
  generateSbom,
  generateScript,
  main,
  openFilesConsole,
  openPort,
  provideHbom,
  provideMetadata,
  provisionWorkbench,
  pythonHelloWorld,
  releaseWorkbench,
  runEvaluate,
  runExperiment,
  SBOM_ARTIFACT_PATH,
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

      // Workspace Snapshot reads the REE's own source declaration and receipt:
      // acquisition names the type from the archive (a .tar.gz is a tarball),
      // an upload has no origin to report, and the receipt carries the SWHID
      // computed over what actually landed in the workspace.
      const snapshot = page.getByRole("region", { name: "Workspace Snapshot" });
      await expect(snapshot.getByText("Origin", { exact: true })).toBeVisible();
      await expect(snapshot.getByText("tarball", { exact: true })).toBeVisible();
      await expect(snapshot.getByText("Size", { exact: true })).toBeVisible();
      await expect(snapshot.getByText(/^swh:1:dir:/)).toBeVisible();
    });

    await test.step("browse uploaded files in the REE tree", async () => {
      await openFilesConsole(page);

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
      // The console browses both inventories the backend publishes, in a section
      // each: the materialized `workspace/`, and the REE tree that excludes it.
      // An uploaded archive lands in `upstream/`, the acquired source, so the
      // filter below narrows to the REE section and these entries are its.
      await page.getByPlaceholder("Filter files…").fill("upstream");
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

    await test.step("generate a build script from the repository", async () => {
      // Read-only inference: it scans the immutable upstream tree, walks the
      // published build DAG, and loads a candidate into the editor. Nothing is
      // written — the build step below authors the script it actually runs.
      await openPort(page, "Build");
      await expect(
        main(page).getByRole("heading", { name: "Build Runtime", exact: true }),
      ).toBeVisible();

      const { message, graph } = await generateScript(page);
      expect(message).toMatch(/Loaded a generated build script/);
      // The project carries both a Dockerfile and a requirements.txt, so both
      // strategies are viable and the result is a decision, not a default.
      expect(message).toMatch(/2 alternatives were available/);
      // The graph is the executed DAG itself — the explanation that must render
      // whether or not a candidate came back.
      expect(graph).toContain("build-inference");
      expect(graph).toContain("single-project-root-dockerfile-v1");

      await expect(page.getByLabel("Build script")).toContainText(/Generated by repo2ree/);
      await expect(page.getByLabel("Build script")).toContainText(/docker build/);
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
      await expect(main(page).getByText("SBOM ready", { exact: true }).first()).toBeVisible();
    });

    await test.step("cross-check SBOM against the scanned dependencies", async () => {
      await crossCheckSbom(page);
    });

    await test.step("generate an activation script from the built runtime", async () => {
      // The runtime artifact now exists and is declared, so inference inspects
      // it directly: the docker plumbing is inferred from the image it finds,
      // while the activation command is deliberately left fail-closed.
      await openPort(page, "Activation");
      await expect(main(page).getByText("Activation Run Script", { exact: true })).toBeVisible();

      const { message, graph } = await generateScript(page);
      expect(message).toMatch(/Loaded a generated activation script/);
      // Phase 1 never auto-selects a run command; the blocking warning says so.
      expect(message).toMatch(/No activation command was selected/);
      expect(graph).toContain("activation-run-inference");

      const editor = main(page).getByRole("textbox", {
        name: "Activation run script",
        exact: true,
      });
      // The scaffold: real docker plumbing around an empty `set --` guarded by
      // exit 64, so it cannot silently run an unconfigured activation.
      await expect(editor).toHaveValue(/docker load --input/);
      await expect(editor).toHaveValue(/exit 64/);
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
        // Exercises experiment inference once the experiment is declared: the
        // scaffold is generated and asserted, then authored over.
        generateFirst: true,
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
      const bundle = Buffer.concat(chunks);
      expect(bundle.includes("ree/results/python-hello/result.txt")).toBe(true);
      // The SBOM was written to the REE's artifacts, so packaging carries it
      // there verbatim — no lift out of the workspace, same path either side.
      expect(bundle.includes(`ree/${SBOM_ARTIFACT_PATH}`)).toBe(true);
    });

    await test.step("release workbench", async () => {
      // Asserts the return to the landing view; the workbenchCleanup fixture
      // then sees a released session and no-ops.
      await releaseWorkbench(page);
    });
  });
});
