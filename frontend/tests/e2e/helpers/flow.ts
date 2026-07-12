import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, type Locator, type Page } from "@playwright/test";
import { stepShot } from "../../screenshot";

/**
 * Lean, reusable steps for driving the REE creation pipeline against a real
 * backend (no mocks). Each helper performs an action and waits on the
 * resulting UI state so callers can compose a precondition for the page they
 * actually want to test, e.g.:
 *
 *   await startReeCreation(page);
 *   await provisionWorkbench(page);
 *   await uploadSource(page, pythonHelloWorld());
 *   await runEvaluate(page);   // <- page under test
 *
 * Unlike the demo spec these add no narration, focus boxes, or artificial
 * waits — they exist for fast regression coverage, not recording.
 */

const RESOURCES_DIR = path.resolve(__dirname, "../../resources");

/** Absolute path to the bundled Python hello-world source archive. */
export function pythonHelloWorld(): string {
  return path.join(RESOURCES_DIR, "examples/python-hello-world.tar.gz");
}

/**
 * Absolute path to the pip-based Python hello-world source archive (no
 * Dockerfile — the workbench itself is the Python runtime). Packed on demand
 * from the checked-in sources into the gitignored test-artifacts dir, so no
 * binary blob lives in the repo.
 */
export function pythonPipHelloWorld(): string {
  const artifactsDir = path.join(process.cwd(), "test-artifacts");
  mkdirSync(artifactsDir, { recursive: true });
  const archive = path.join(artifactsDir, "python-pip-hello-world.tar.gz");
  execFileSync("tar", [
    "-czf",
    archive,
    "-C",
    path.join(RESOURCES_DIR, "examples"),
    "python_pip_hello_world",
  ]);
  return archive;
}

/**
 * A self-contained run script for a runnable (activation or experiment). In the
 * new model each runnable owns its full execution: load the built runtime image
 * if it isn't already present, then enter it with its own `docker run`,
 * bind-mounting the workspace so declared file outputs surface on the host.
 *
 * When `outputFile` is given the run's stdout is materialized to that
 * workspace-relative file (via `tee`) so a verify script can read it back —
 * there are no magic variables handing stdout to verification.
 */
export function dockerRunScript(command: string, runtimePath: string, outputFile?: string): string {
  const capture = outputFile ? ` | tee ${JSON.stringify(outputFile)}` : "";
  return `#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
RUNTIME_FILE=${JSON.stringify(runtimePath)}

if ! docker image inspect "$IMAGE_NAME:$TAG" >/dev/null 2>&1; then
  docker load < "$RUNTIME_FILE"
fi

docker run --rm \\
  -v "$(pwd):/workspace" \\
  -w /workspace \\
  "$IMAGE_NAME:$TAG" \\
  ${command}${capture}
`;
}

/**
 * Workspace file the experiment run script materializes its stdout to. Declared
 * as the experiment's output (see `runExperiment`) so a successful run captures
 * it into the produced-results store, and sealed into the bundle as the author
 * baseline a reviewer diffs against.
 */
export const EXPERIMENT_OUTPUT_FILE = "result.txt";

export function main(page: Page) {
  return page.getByRole("main");
}

function waitForIntentPatch(page: Page) {
  return page.waitForResponse(
    (res) => res.url().includes("/intent") && res.request().method() === "PATCH",
  );
}

/**
 * The canvas hub. Navigation lives here as pod "nodes" (Source, Metadata,
 * Reproducibility Readiness, Build, Hardware, Experiments, Archive, Seal) floating around
 * the specimen pod — scope clicks here so short node labels don't collide with
 * same-named main buttons.
 */
function nav(page: Page) {
  return page.getByRole("navigation");
}

/**
 * Open a hub node by its exact label. When a page is already docked its scrim
 * covers the constellation, so fly back out (Escape) before picking the next
 * node — the same "close, then choose" motion a user performs.
 */
export async function openPort(page: Page, label: string) {
  await page.keyboard.press("Escape").catch(() => {});
  await nav(page).getByRole("button", { name: label, exact: true }).click();
}

/**
 * How many connected agents the lab-location picker offers. Specs that need
 * more than one agent (multi-agent, stress) call this first and skip when the
 * stack is smaller — the count is a property of whatever stack the suite runs
 * against (source, image, or published), not something the tests control.
 */
export async function connectedAgentCount(page: Page): Promise<number> {
  await page.goto("/");
  await page.getByRole("button", { name: "Create REE" }).click();
  await expect(page.getByRole("heading", { name: "Choose a lab location" })).toBeVisible();
  const cards = page.getByRole("button", { name: /connected/ });
  // The agent list loads async; a suite-worthy stack always has at least one
  // agent, so waiting for the first card is enough for a settled count.
  await cards.first().waitFor({ state: "visible" });
  return cards.count();
}

/**
 * Land on the workbench lab from the landing view. REE creation now opens with
 * the lab-location step: pick the (connected) agent that will host the
 * workbench, which carries its id into the workbench/image page.
 *
 * `agentIndex` picks the nth connected agent (default: the first) — the
 * multi-agent spec uses it to pin each session to a different agent. Returns
 * the chosen agent's id, read back from the workspace URL the picker
 * navigates to.
 */
export async function startReeCreation(page: Page, options?: { agentIndex?: number }) {
  await page.goto("/");
  await stepShot(page, "start-ree-creation", "before");
  await page.getByRole("button", { name: "Create REE" }).click();
  await expect(page.getByRole("heading", { name: "Choose a lab location" })).toBeVisible();
  await page
    .getByRole("button", { name: /connected/ })
    .nth(options?.agentIndex ?? 0)
    .click();
  await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
  await stepShot(page, "start-ree-creation", "after");
  return new URL(page.url()).searchParams.get("agentId") ?? "";
}

/**
 * Provision the workbench container. Provisioning now lands on the hub canvas
 * (the live lab), so this resolves there and then dives into the Source node so
 * the rest of the walkthrough continues from a docked page.
 */
export async function provisionWorkbench(page: Page, options?: { imageRef?: string }) {
  await stepShot(page, "provision-workbench", "before");
  if (options?.imageRef) {
    // Pick "Custom…" in the image selector and provide the reference — the
    // catalog default (docker:dind) stays untouched for every other test.
    await page.getByRole("button", { name: /Custom…/ }).click();
    await page.getByPlaceholder("e.g. docker.io/library/docker:29-dind").fill(options.imageRef);
  }
  await page.getByRole("button", { name: /Provision workbench/i }).click();
  // A real provision: bench container start, nested dockerd boot, doctor
  // probe. ~15-20s depending on the agent's environment — well past the
  // project's default expect timeout.
  await expect(nav(page).getByRole("button", { name: "Source", exact: true })).toBeVisible({
    timeout: 90000,
  });
  await openPort(page, "Source");
  await expect(
    page.getByRole("region", { name: "Source Acquisition" }).getByText("Source Acquisition", {
      exact: true,
    }),
  ).toBeVisible();
  await stepShot(page, "provision-workbench", "after");
}

/** Upload a tarball into the workspace and wait for the snapshot to settle. */
export async function uploadSource(page: Page, archivePath: string) {
  await stepShot(page, "upload-source", "before");
  await page.getByRole("button", { name: "Upload tarball" }).click();
  await page
    .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
    .setInputFiles(archivePath);
  await page.getByRole("button", { name: /Add to workspace/i }).click();

  // The clear-source action lives in the source hub panel header (top-right).
  const clearSource = page
    .getByRole("region", { name: "Source Acquisition" })
    .getByRole("button", { name: /Clear source/i });
  await expect(clearSource).toBeVisible();
  await stepShot(page, "upload-source", "after");
  return clearSource;
}

/**
 * Fetch a source from an origin URL (the "Use origin URL" path) and wait for the
 * snapshot to settle. Selects the source type first so the git-only revision
 * field renders before it is filled; leave `revision` blank to fetch HEAD.
 */
export async function downloadSource(
  page: Page,
  origin: { url: string; sourceType?: "git" | "tarball" | "zip"; revision?: string },
) {
  await stepShot(page, "download-source", "before");
  const region = page.getByRole("region", { name: "Source Acquisition" });
  await region.getByRole("button", { name: "Use origin URL", exact: true }).click();
  await page.getByPlaceholder("https://github.com/org/repo").fill(origin.url);
  await region.getByRole("combobox").selectOption(origin.sourceType ?? "git");
  if (origin.revision) {
    await page.getByPlaceholder(/Revision \(commit, branch, or tag\)/).fill(origin.revision);
  }
  await region.getByRole("button", { name: /Download source to workspace/i }).click();

  // A real git fetch against a remote (cold, no cache) — allow a generous budget.
  const clearSource = region.getByRole("button", { name: /Clear source/i });
  await expect(clearSource).toBeVisible({ timeout: 90000 });
  await stepShot(page, "download-source", "after");
  return clearSource;
}

/** Fill in project identity metadata. */
export async function provideMetadata(
  page: Page,
  meta: { name: string; version: string; description: string },
) {
  await stepShot(page, "provide-metadata", "before");
  await openPort(page, "Metadata");
  await expect(main(page).getByRole("heading", { name: "Metadata", exact: true })).toBeVisible();
  await page.getByPlaceholder("deepfold-protein-structure-prediction").fill(meta.name);
  await page.getByPlaceholder("1.0.0").fill(meta.version);
  await page.getByPlaceholder("REE for reproducible execution of...").fill(meta.description);
  await stepShot(page, "provide-metadata", "after");
}

/** Run dependency evaluation and wait for the score to be produced. */
export async function runEvaluate(page: Page) {
  await stepShot(page, "run-evaluate", "before");
  await openPort(page, "Reproducibility Readiness");
  await expect(main(page).getByText("Reproducibility Readiness", { exact: true })).toBeVisible();
  await main(page)
    .getByRole("button", { name: /^Run Evaluate$/ })
    .click();
  await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible({
    timeout: 20000,
  });
  await stepShot(page, "run-evaluate", "after");
}

/**
 * Build the runtime artifact and select the produced file. Both building and
 * picking the produced artifact now live on the single Build Runtime page — see
 * {@link selectRuntimeArtifact}.
 */
export function dockerBuildScript(projectDir: string, producedRuntimePath: string): string {
  return `#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
PROJECT_DIR=${JSON.stringify(projectDir)}
RUNTIME_FILE=${JSON.stringify(producedRuntimePath)}

docker build -t "$IMAGE_NAME:$TAG" "$PROJECT_DIR"
docker save "$IMAGE_NAME:$TAG" -o "$RUNTIME_FILE"
`;
}

export async function buildRuntime(page: Page, buildScript: string, producedRuntimePath: string) {
  await stepShot(page, "build-runtime", "before");
  await openPort(page, "Build");
  await expect(main(page).getByText("Build Runtime", { exact: true })).toBeVisible();
  // REE owns one reserved build script — author the whole build in it directly
  // (produce the runtime artifact and land it in the workspace).
  await page.getByLabel("Build script").fill(buildScript);
  await main(page).getByRole("button", { name: "Save build script" }).click();

  await main(page)
    .getByRole("button", { name: /Run build/ })
    .click();
  // DinD: each workbench daemon starts with an empty image cache, so the first
  // build is a cold pull + install (~30s+), not a warm shared-cache build.
  await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible({
    timeout: 90000,
  });

  // Re-build appears for failed runs too. The earned-outcome badge
  // (role="status") renders only for a succeeded run, so a failed build fails
  // this step with its log on screen instead of surfacing 20s later as an
  // artifact-picker timeout.
  await expect(main(page).getByRole("status", { name: "Built" })).toBeVisible();

  await selectRuntimeArtifact(page, producedRuntimePath);
  await stepShot(page, "build-runtime", "after");
}

/**
 * Author a runnable's run script: fill the RunScriptCard textarea, then click
 * its "Save run script" button (shared by the activation and experiment
 * editors).
 */
async function saveRunScript(page: Page, editor: Locator, content: string) {
  await editor.fill(content);
  await main(page).getByRole("button", { name: "Save run script", exact: true }).first().click();
}

/** Author and declare a runnable's verify script. */
async function saveVerifyScript(page: Page, editor: Locator, content: string) {
  await editor.fill(content);
  await main(page).getByRole("button", { name: "Save verify script", exact: true }).first().click();
}

function stdoutContainsVerifyScript(expectedStdout: string): string {
  return `#!/usr/bin/env sh
set -eu

# The run script materialized its stdout to this workspace file; read it back.
EXPECTED=${JSON.stringify(expectedStdout)}
grep -Fq "$EXPECTED" ${JSON.stringify(EXPERIMENT_OUTPUT_FILE)}
`;
}

/**
 * Pick the produced runtime artifact. The runtime artifact card now lives on the
 * Build Runtime page itself (section "1. Build or acquire the runtime"), so this
 * just picks the produced file via the repository file picker right where the
 * build ran — no pod decomposition needed.
 */
async function selectRuntimeArtifact(page: Page, producedRuntimePath: string) {
  await page
    .getByPlaceholder("runtime.tar.gz")
    .locator("..")
    .getByTitle("Browse repository files")
    .click();
  const producedRuntime = page.getByRole("button", { name: producedRuntimePath });
  await expect(producedRuntime).toBeVisible({ timeout: 20000 });
  await producedRuntime.click();
}

/** Add a hardware BOM entry (a CPU component with a device model). */
export async function provideHbom(page: Page, cpuModel: string) {
  await stepShot(page, "provide-hbom", "before");
  await openPort(page, "Hardware");
  await expect(main(page).getByText("Hardware BOM", { exact: true })).toBeVisible();
  await main(page).locator("button").filter({ hasText: "Add CPU" }).first().click();
  const deviceModel = main(page).getByPlaceholder("Intel Core i9-14900K").first();
  await deviceModel.fill(cpuModel);
  await expect(deviceModel).toHaveValue(cpuModel);
  await stepShot(page, "provide-hbom", "after");
}

/**
 * Generate the SBOM. Navigates to the SBOM canvas node (a standalone page).
 */
export async function generateSbom(page: Page) {
  await stepShot(page, "generate-sbom", "before");
  await openPort(page, "SBOM");
  const panel = page.getByRole("region", { name: "Generate SBOM" });
  await expect(panel.getByRole("button", { name: /^Generate$/ })).toBeVisible();
  await panel.getByRole("button", { name: /^Generate$/ }).click();
  await expect(panel.getByRole("button", { name: /^Regenerate$/ })).toBeVisible({
    timeout: 20000,
  });
  await expect(panel.getByText("SBOM ready", { exact: true }).first()).toBeVisible({
    timeout: 20000,
  });
  await stepShot(page, "generate-sbom", "after");
}

/**
 * Author and run the activation. Navigates to the Activation canvas node (a
 * standalone page) and authors the given self-contained run script (e.g.
 * {@link dockerRunScript}) that proves the built runtime starts.
 */
export async function testActivation(page: Page, runScript: string) {
  await stepShot(page, "test-activation", "before");
  await openPort(page, "Activation");
  await expect(main(page).getByText("Activation Run Script", { exact: true })).toBeVisible();
  await saveRunScript(
    page,
    main(page).getByRole("textbox", { name: "Activation run script", exact: true }),
    runScript,
  );
  await main(page)
    .getByRole("button", { name: /Run activation/ })
    .click();
  // DinD: cold `docker load` of the runtime image + run (no shared cache).
  await expect(main(page).getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 90000 });
  // Re-run appears for failed runs too; the earned-outcome badge is
  // success-only.
  await expect(main(page).getByRole("status", { name: "Activation passed" })).toBeVisible();
  await stepShot(page, "test-activation", "after");
}

/**
 * Define a single experiment, author its run and verify scripts, run it, and
 * wait for it to pass. Like activation, the experiment owns its full run via
 * the given script, which must tee its stdout to {@link EXPERIMENT_OUTPUT_FILE}
 * (e.g. `dockerRunScript(cmd, runtime, EXPERIMENT_OUTPUT_FILE)`). The verify
 * script owns the claim, reading that file back — its exit code is the verdict.
 */
export async function runExperiment(
  page: Page,
  experiment: { name: string; runScript: string; expectedStdout: string },
) {
  await stepShot(page, "run-experiment", "before");
  await openPort(page, "Experiments");
  await expect(main(page).getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();
  const experimentAdded = waitForIntentPatch(page);
  await main(page)
    .getByRole("button", { name: /Add experiment/i })
    .first()
    .click();
  await experimentAdded;

  const nameSaved = waitForIntentPatch(page);
  await main(page).getByPlaceholder("smoke-test").fill(experiment.name);
  await nameSaved;

  const runScriptDeclared = waitForIntentPatch(page);
  await saveRunScript(
    page,
    main(page).getByRole("textbox", { name: "Experiment run script", exact: true }),
    experiment.runScript,
  );
  await runScriptDeclared;

  // Saving the verify script also declares its fallback reserved path on the
  // experiment intent. Arm the wait before the save so the run can't race ahead
  // of the debounced intent PATCH that makes the backend see the verify script.
  const verifyScriptDeclared = waitForIntentPatch(page);
  await saveVerifyScript(
    page,
    main(page).getByRole("textbox", { name: "Experiment verify script", exact: true }),
    stdoutContainsVerifyScript(experiment.expectedStdout),
  );
  await verifyScriptDeclared;

  // Declare the produced result file so a successful run captures it. Including
  // it in the bundle is a seal-time choice made on the Seal page (defaults on
  // once an output is declared), so there is nothing to opt into here.
  const outputDeclared = waitForIntentPatch(page);
  await main(page).getByRole("textbox", { name: "Output files" }).fill(EXPERIMENT_OUTPUT_FILE);
  await outputDeclared;

  await main(page).getByRole("button", { name: /^Run$/ }).click();
  // Fail fast with a clear signal if the click was still dropped: a started
  // run flips the header button to Running…/Re-run within moments.
  await expect(main(page).getByRole("button", { name: /Running…|Re-run/ })).toBeVisible({
    timeout: 10000,
  });
  const runResult = main(page)
    .locator("div")
    .filter({ hasText: /^Run result/ })
    .first();
  // DinD: cold runtime-image load + container run on the per-REE daemon —
  // the heaviest wait in the suite, and the first to blow its budget when
  // the host is under load. Keep it roomier than the other 90s steps.
  await expect(runResult.getByText("pass", { exact: true })).toBeVisible({ timeout: 180000 });
  await expect(runResult.getByText(/claimed result was reproduced/)).toBeVisible();
  await stepShot(page, "run-experiment", "after");
}

/**
 * Seal the REE. Uses the "Seal anyway" path so it works regardless of how
 * complete the REE is — sealing is what makes the workbench release control
 * appear.
 */
/** The seal panel pinned inside the constellation hub (not the docked main area). */
function sealPanel(page: Page) {
  return page.getByRole("region", { name: "Seal" });
}

export async function sealRee(page: Page) {
  await stepShot(page, "seal-ree", "before");
  await openPort(page, "Seal");
  const sealButton = sealPanel(page)
    .getByRole("button", { name: /Seal (REE|anyway)/ })
    .first();
  await expect(sealButton).toBeVisible();
  await sealButton.click();
  await expect(sealPanel(page).getByText("REE SEALED", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await stepShot(page, "seal-ree", "after");
}

/** Release (tear down) the workbench container; returns to the landing view. */
export async function releaseWorkbench(page: Page) {
  await stepShot(page, "release-workbench", "before");
  // The release button lives inside the bench console HUD (bottom-left). Open
  // the console first, then click the button.
  await page.keyboard.press("Escape").catch(() => {});
  await page.getByRole("button", { name: /Expand workbench console/i }).click();
  const releaseButton = page.getByRole("button", { name: /Release workbench/i }).first();
  await expect(releaseButton).toBeVisible();
  await releaseButton.click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: /Create REE/i })).toBeVisible();
  await stepShot(page, "release-workbench", "after");
}

/**
 * Best-effort teardown for the workbench container a test provisioned. Releases
 * it via the bench console. Safe to call after any test — it no-ops when no
 * provisioned session is present.
 */
export async function cleanupWorkbench(page: Page) {
  // Only meaningful inside a provisioned editor session. A test that ended back
  // on the landing view (e.g. already released) has nothing to clean up.
  if (!page.url().includes("/workspace")) {
    return;
  }

  // The Seal node is locked (disabled) until the workbench is provisioned; if it
  // isn't enabled the test never provisioned — no container to release.
  const sealNav = nav(page).getByRole("button", { name: "Seal", exact: true });
  if (!(await sealNav.isEnabled().catch(() => false))) {
    return;
  }

  await releaseWorkbench(page);
}
