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
 * A self-contained run script for a runnable (activation or experiment). In the
 * new model each runnable owns its full execution: load the built runtime image
 * if it isn't already present, then enter it with its own `docker run`,
 * bind-mounting the workspace so declared file outputs surface on the host.
 */
function dockerRunScript(command: string, runtimePath: string): string {
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
  ${command}
`;
}

export function main(page: Page) {
  return page.getByRole("main");
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
 * Land on the workbench lab from the landing view. REE creation now opens with
 * the lab-location step: pick the (connected) agent that will host the
 * workbench, which carries its id into the workbench/image page.
 */
export async function startReeCreation(page: Page) {
  await page.goto("/");
  await stepShot(page, "start-ree-creation", "before");
  await page.getByRole("button", { name: "Create REE" }).click();
  await expect(page.getByRole("heading", { name: "Choose a lab location" })).toBeVisible();
  await page
    .getByRole("button", { name: /connected/ })
    .first()
    .click();
  await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
  await stepShot(page, "start-ree-creation", "after");
}

/**
 * Provision the workbench container. Provisioning now lands on the hub canvas
 * (the live lab), so this resolves there and then dives into the Source node so
 * the rest of the walkthrough continues from a docked page.
 */
export async function provisionWorkbench(page: Page) {
  await stepShot(page, "provision-workbench", "before");
  await page.getByRole("button", { name: /Provision workbench/i }).click();
  await expect(nav(page).getByRole("button", { name: "Source", exact: true })).toBeVisible();
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
export async function buildRuntime(page: Page, projectDir: string, producedRuntimePath: string) {
  await stepShot(page, "build-runtime", "before");
  await openPort(page, "Build");
  await expect(main(page).getByText("Build Runtime", { exact: true })).toBeVisible();
  // REE owns one reserved build script — author the whole build in it directly
  // (build the image from the project Dockerfile, save it to the workspace).
  await page.getByLabel("Build script").fill(`#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
PROJECT_DIR=${JSON.stringify(projectDir)}
RUNTIME_FILE=${JSON.stringify(producedRuntimePath)}

docker build -t "$IMAGE_NAME:$TAG" "$PROJECT_DIR"
docker save "$IMAGE_NAME:$TAG" -o "$RUNTIME_FILE"
`);
  await main(page).getByRole("button", { name: "Save build script" }).click();

  await main(page)
    .getByRole("button", { name: /Run build/ })
    .click();
  // DinD: each workbench daemon starts with an empty image cache, so the first
  // build is a cold pull + install (~30s+), not a warm shared-cache build.
  await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible({
    timeout: 90000,
  });

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
 * standalone page) and authors a self-contained run script that loads the built
 * image and enters it with `docker run` to prove it starts.
 */
export async function testActivation(page: Page, command: string, runtimePath: string) {
  await stepShot(page, "test-activation", "before");
  await openPort(page, "Activation");
  await expect(main(page).getByText("Activation Run Script", { exact: true })).toBeVisible();
  await saveRunScript(
    page,
    main(page).getByRole("textbox", { name: "Activation run script", exact: true }),
    dockerRunScript(command, runtimePath),
  );
  await main(page)
    .getByRole("button", { name: /Run activation/ })
    .click();
  // DinD: cold `docker load` of the runtime image + run (no shared cache).
  await expect(main(page).getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 90000 });
  await stepShot(page, "test-activation", "after");
}

/**
 * Define a single experiment, author its run script, run it, and wait for it to
 * pass. Like activation, the experiment owns its full run: load the image and
 * `docker run` the command in the bind-mounted workspace.
 */
export async function runExperiment(
  page: Page,
  experiment: { name: string; command: string; expectedStdout: string; runtimePath: string },
) {
  await stepShot(page, "run-experiment", "before");
  await openPort(page, "Experiments");
  await expect(main(page).getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();
  await main(page)
    .getByRole("button", { name: /Add experiment/i })
    .first()
    .click();
  await main(page).getByPlaceholder("smoke-test").fill(experiment.name);
  await saveRunScript(
    page,
    main(page).getByRole("textbox", { name: "Experiment run script", exact: true }),
    dockerRunScript(experiment.command, experiment.runtimePath),
  );
  const outputsCard = main(page)
    .locator("div")
    .filter({ hasText: /^Expected outputs/ })
    .first();
  await outputsCard.getByRole("button", { name: /Add/ }).first().click();
  await main(page).getByPlaceholder("PASSED").first().fill(experiment.expectedStdout);
  await main(page).getByRole("button", { name: /^Run$/ }).click();
  const runResult = main(page)
    .locator("div")
    .filter({ hasText: /^Run result/ })
    .first();
  // DinD: cold runtime-image load + container run on the per-REE daemon.
  await expect(runResult.getByText("pass", { exact: true })).toBeVisible({ timeout: 90000 });
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
async function releaseWorkbench(page: Page) {
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
