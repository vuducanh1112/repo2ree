import path from "node:path";
import { expect, type Page } from "@playwright/test";
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

export function main(page: Page) {
  return page.getByRole("main");
}

/**
 * The canvas hub. Navigation lives here as pod "nodes" (Source, Metadata,
 * Repro Label, Runtime, Hardware, Experiments, Archive, Seal) floating around
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
async function openPort(page: Page, label: string) {
  await page.keyboard.press("Escape").catch(() => {});
  await nav(page).getByRole("button", { name: label, exact: true }).click();
}

/** Land on the workbench lab (first screen of REE creation) from the landing view. */
export async function startReeCreation(page: Page) {
  await page.goto("/");
  await stepShot(page, "start-ree-creation", "before");
  await page.getByRole("button", { name: "Create REE" }).click();
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
  await expect(main(page).getByText("Source Acquisition", { exact: true })).toBeVisible();
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

  // The clear-source action now lives in the page header (top-right), no longer
  // inside the Workspace Snapshot block.
  const clearSource = main(page).getByRole("button", { name: /Clear source/i });
  await expect(clearSource).toBeVisible();
  await stepShot(page, "upload-source", "after");
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
  await openPort(page, "Repro Label");
  await expect(main(page).getByText("Evaluate", { exact: true })).toBeVisible();
  await main(page)
    .getByRole("button", { name: /^Play Run Evaluate$/ })
    .click();
  await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible({
    timeout: 20000,
  });
  await stepShot(page, "run-evaluate", "after");
}

/**
 * Build the runtime artifact and select the produced file. The Runtime node
 * reads as done once the artifact is selected; whether it is bundled into the
 * REE is chosen later in the hub's seal panel, not here.
 */
export async function buildRuntime(
  page: Page,
  buildScriptPath: string,
  producedRuntimePath: string,
) {
  await stepShot(page, "build-runtime", "before");
  await openPort(page, "Runtime");
  await expect(main(page).getByText("Runtime Environment", { exact: true })).toBeVisible();
  await page.getByPlaceholder("build_runtime.sh").fill(buildScriptPath);
  await main(page)
    .getByRole("button", { name: /Run build/ })
    .click();
  // DinD: each workbench daemon starts with an empty image cache, so the first
  // build is a cold pull + install (~30s+), not a warm shared-cache build.
  await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible({
    timeout: 90000,
  });

  // Select the produced runtime artifact via the repository file picker.
  await page
    .getByPlaceholder("runtime.tar.gz")
    .locator("..")
    .getByTitle("Browse repository files")
    .click();
  const producedRuntime = page.getByRole("button", { name: producedRuntimePath });
  await expect(producedRuntime).toBeVisible({ timeout: 20000 });
  await producedRuntime.click();
  await stepShot(page, "build-runtime", "after");
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
 * Generate the SBOM. Assumes the runtime has been built and included (the scan
 * target defaults to it). Switches to the "Generate SBOM" tab on the Runtime
 * Environment page, so call after {@link buildRuntime}.
 */
export async function generateSbom(page: Page) {
  await stepShot(page, "generate-sbom", "before");
  const tab = main(page).locator("button[aria-pressed]").filter({ hasText: "Generate SBOM" });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-pressed", "true");
  await expect(main(page).getByText("Scan Target", { exact: true })).toBeVisible();
  await main(page)
    .getByRole("button", { name: /Generate SBOM/ })
    .last()
    .click();
  await expect(main(page).getByRole("button", { name: /Regenerate SBOM/ })).toBeVisible({
    timeout: 20000,
  });
  await expect(main(page).getByText("SBOM ready", { exact: true }).first()).toBeVisible({
    timeout: 20000,
  });
  await stepShot(page, "generate-sbom", "after");
}

/**
 * Run the runtime activation test from the given script path. Switches to the
 * "Test Activation" tab on the Runtime Environment page, so call after
 * {@link buildRuntime}.
 */
export async function testActivation(page: Page, activationScriptPath: string) {
  await stepShot(page, "test-activation", "before");
  const tab = main(page).locator("button[aria-pressed]").filter({ hasText: "Test Activation" });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-pressed", "true");
  await expect(main(page).getByText("Activation Script", { exact: true })).toBeVisible();
  await main(page).getByPlaceholder("activation_test.sh").first().fill(activationScriptPath);
  await main(page)
    .getByRole("button", { name: /Run activation/ })
    .click();
  // DinD: cold `docker load` of the runtime image + run (no shared cache).
  await expect(main(page).getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 90000 });
  await stepShot(page, "test-activation", "after");
}

/** Define a single experiment, run it, and wait for it to pass. */
export async function runExperiment(
  page: Page,
  experiment: { name: string; command: string; expectedStdout: string },
) {
  await stepShot(page, "run-experiment", "before");
  await openPort(page, "Experiments");
  await expect(main(page).getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();
  await main(page)
    .getByRole("button", { name: /Add experiment/i })
    .first()
    .click();
  await main(page).getByPlaceholder("smoke-test").fill(experiment.name);
  await main(page).getByPlaceholder("pytest tests/smoke -q").fill(experiment.command);
  const outputsCard = main(page)
    .locator("div")
    .filter({ hasText: /^Expected outputs/ })
    .first();
  await outputsCard.getByRole("button", { name: /Add/ }).first().click();
  await main(page).getByPlaceholder("PASSED").first().fill(experiment.expectedStdout);
  await main(page)
    .getByRole("button", { name: /^Play Run$/ })
    .click();
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
export function sealPanel(page: Page) {
  return page.getByRole("region", { name: "Seal" });
}

export async function sealRee(page: Page) {
  await stepShot(page, "seal-ree", "before");
  await openPort(page, "Seal");
  await expect(sealPanel(page).getByText("Seal REE", { exact: true })).toBeVisible();
  await sealPanel(page).getByRole("button", { name: /Seal/ }).first().click();
  await expect(sealPanel(page).getByText("Seal this REE?", { exact: true })).toBeVisible();
  await sealPanel(page)
    .getByRole("button", { name: /Seal (REE|anyway)/ })
    .click();
  await expect(sealPanel(page).getByText("REE SEALED", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await stepShot(page, "seal-ree", "after");
}

/** Release (tear down) the workbench container; returns to the landing view. */
async function releaseWorkbench(page: Page) {
  await stepShot(page, "release-workbench", "before");
  const releaseButton = sealPanel(page)
    .getByRole("button", { name: /Release workbench/i })
    .first();
  await expect(releaseButton).toBeVisible();
  await releaseButton.click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: /Create REE/i })).toBeVisible();
  await stepShot(page, "release-workbench", "after");
}

/**
 * Best-effort teardown for the workbench container a test provisioned. Seals
 * the REE (so the release control appears) and releases it. Safe to call after
 * any test — it no-ops when no provisioned session is present, and skips
 * sealing when the REE is already sealed.
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

  // The sealed state shows only while the hub's seal panel is open, so open it
  // before deciding whether sealing is still needed.
  await openPort(page, "Seal");
  const alreadySealed = await sealPanel(page)
    .getByText("REE SEALED", { exact: true })
    .isVisible()
    .catch(() => false);

  if (!alreadySealed) {
    await sealRee(page);
  }

  await releaseWorkbench(page);
}
