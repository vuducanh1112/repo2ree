import path from "node:path";
import { expect, type Page } from "@playwright/test";

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

/** Assert the overview "cable" for a pipeline step shows as completed. */
async function expectOverviewCableActive(page: Page, label: string) {
  await expect(page.getByText(`✓ ${label}`, { exact: true })).toBeVisible();
}

/** Land on the workbench page from the landing view. */
export async function startReeCreation(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Create REE" }).click();
  await expect(main(page).getByText("Workbench", { exact: true })).toBeVisible();
}

/** Provision the workbench container; resolves once Source Acquisition shows. */
export async function provisionWorkbench(page: Page) {
  await page.getByRole("button", { name: /Provision workbench/i }).click();
  await expect(main(page).getByText("Source Acquisition", { exact: true })).toBeVisible();
}

/** Upload a tarball into the workspace and wait for the snapshot to settle. */
export async function uploadSource(page: Page, archivePath: string) {
  await page.getByRole("button", { name: "Upload tarball" }).click();
  await page
    .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
    .setInputFiles(archivePath);
  await page.getByRole("button", { name: /Add to workspace/i }).click();

  const workspaceActions = page
    .locator("div")
    .filter({ hasText: "Workspace Snapshot" })
    .filter({ hasText: /Browse workspace files/ })
    .first();
  await expect(workspaceActions).toBeVisible();
  return workspaceActions;
}

/** Fill in project identity metadata. */
export async function provideMetadata(
  page: Page,
  meta: { name: string; version: string; description: string },
) {
  await page.getByRole("button", { name: /Provide Metadata.*project identity metadata/i }).click();
  await expect(main(page).getByRole("heading", { name: "Metadata", exact: true })).toBeVisible();
  await page.getByPlaceholder("deepfold-protein-structure-prediction").fill(meta.name);
  await page.getByPlaceholder("1.0.0").fill(meta.version);
  await page.getByPlaceholder("REE for reproducible execution of...").fill(meta.description);
}

/** Run dependency evaluation and wait for the score to be produced. */
export async function runEvaluate(page: Page) {
  await page.getByRole("button", { name: /Evaluate.*Score reproducibility level/ }).click();
  await expect(main(page).getByText("Evaluate", { exact: true })).toBeVisible();
  await main(page)
    .getByRole("button", { name: /^Play Run Evaluate$/ })
    .click();
  await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible({
    timeout: 20000,
  });
  await expectOverviewCableActive(page, "Evaluate");
}

/**
 * Build the runtime artifact and select the produced file. The Runtime cable
 * activates once the artifact is selected; whether it is bundled into the REE
 * is chosen later in the seal window, not here.
 */
export async function buildRuntime(
  page: Page,
  buildScriptPath: string,
  producedRuntimePath: string,
) {
  await page
    .getByRole("button", { name: /Runtime Environment.*Build, inventory, and verify runtime/ })
    .click();
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

  // Selecting the artifact is enough to activate the Runtime cable; bundling is
  // decided in the seal window.
  await expectOverviewCableActive(page, "Runtime");
}

/** Add a hardware BOM entry (a CPU component with a device model). */
export async function provideHbom(page: Page, cpuModel: string) {
  await page.getByRole("button", { name: /Create HBOM.*Enter hardware bill of materials/ }).click();
  await expect(main(page).getByText("Hardware BOM", { exact: true })).toBeVisible();
  await main(page).locator("button").filter({ hasText: "Add CPU" }).first().click();
  const deviceModel = main(page).getByPlaceholder("Intel Core i9-14900K").first();
  await deviceModel.fill(cpuModel);
  await expect(deviceModel).toHaveValue(cpuModel);
}

/**
 * Generate the SBOM. Assumes the runtime has been built and included (the scan
 * target defaults to it). Switches to the "Generate SBOM" tab on the Runtime
 * Environment page, so call after {@link buildRuntime}.
 */
export async function generateSbom(page: Page) {
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
  await expectOverviewCableActive(page, "SBOM");
}

/**
 * Run the runtime activation test from the given script path. Switches to the
 * "Test Activation" tab on the Runtime Environment page, so call after
 * {@link buildRuntime}.
 */
export async function testActivation(page: Page, activationScriptPath: string) {
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
  await expectOverviewCableActive(page, "Activation");
}

/** Define a single experiment, run it, and wait for it to pass. */
export async function runExperiment(
  page: Page,
  experiment: { name: string; command: string; expectedStdout: string },
) {
  await page
    .getByRole("button", { name: /Experiments.*Define reproducibility experiment commands/ })
    .click();
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
}

/**
 * Seal the REE. Uses the "Seal anyway" path so it works regardless of how
 * complete the REE is — sealing is what makes the workbench release control
 * appear.
 */
export async function sealRee(page: Page) {
  await page.getByRole("button", { name: /Seal.*Seal the REE/ }).click();
  await expect(main(page).getByText("Seal REE", { exact: true })).toBeVisible();
  await main(page).getByRole("button", { name: /Seal/ }).first().click();
  await expect(main(page).getByText("Seal this REE?", { exact: true })).toBeVisible();
  await main(page)
    .getByRole("button", { name: /Seal (REE|anyway)/ })
    .click();
  await expect(main(page).getByText("REE SEALED", { exact: true })).toBeVisible({
    timeout: 20000,
  });
}

/** Release (tear down) the workbench container; returns to the landing view. */
async function releaseWorkbench(page: Page) {
  const releaseButton = main(page)
    .getByRole("button", { name: /Release workbench/i })
    .first();
  await expect(releaseButton).toBeVisible();
  await releaseButton.click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: /Create REE/i })).toBeVisible();
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

  const alreadySealed = await main(page)
    .getByText("REE SEALED", { exact: true })
    .isVisible()
    .catch(() => false);

  if (!alreadySealed) {
    // If the Seal step isn't reachable the workbench was never provisioned
    // (e.g. the test failed before provisioning) — no container to release.
    const sealNav = page.getByRole("button", { name: /Seal.*Seal the REE/ });
    if (!(await sealNav.isVisible().catch(() => false))) {
      return;
    }
    await sealRee(page);
  }

  await releaseWorkbench(page);
}
