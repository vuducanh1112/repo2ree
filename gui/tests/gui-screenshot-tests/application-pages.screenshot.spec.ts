import { expect, test } from "@playwright/test";
import { installVisualScenario } from "./fixtures/scenario";
import { openVisualWorkspace, openWorkspacePage, settleVisualPage } from "./helpers/visualPage";

test.beforeEach(async ({ page }) => {
  await installVisualScenario(page);
});

test("landing page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "REE Workspace" })).toBeVisible();
  await settleVisualPage(page);
  await expect(page).toHaveScreenshot("landing.png");
});

test("lab location picker", async ({ page }) => {
  await page.goto("/lab-location");
  await expect(page.getByRole("heading", { name: "Choose a lab location" })).toBeVisible();
  await expect(page.getByText("lab-oslo-01")).toBeVisible();
  await settleVisualPage(page);
  await expect(page).toHaveScreenshot("lab-location.png");
});

test("workbench setup", async ({ page }) => {
  await page.goto("/workspace?agentId=agent-oslo");
  await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
  await expect(page.getByText("Python 3.12")).toBeVisible();
  await settleVisualPage(page);
  await expect(page).toHaveScreenshot("workbench-setup.png");
});

test("REE index", async ({ page }) => {
  await page.goto("/ree-index");
  await expect(page.getByRole("heading", { name: "REE Index" })).toBeVisible();
  await expect(page.getByText("climate-model-lab")).toBeVisible();
  await settleVisualPage(page);
  await expect(page).toHaveScreenshot("ree-index.png");
});

test("authored workspace hub", async ({ page }) => {
  await openVisualWorkspace(page);
  await expect(page).toHaveScreenshot("workspace-hub.png");
});

test("completed review", async ({ page }) => {
  await openVisualWorkspace(page);
  await page.getByRole("button", { name: "Expand review controls" }).click();
  await expect(page.getByText("RESULTS · 1/1 REPRODUCED")).toBeVisible();
  await settleVisualPage(page);
  await expect(page).toHaveScreenshot("review-complete.png");
});

test("source workspace", async ({ page }) => {
  await openWorkspacePage(page, "Source");
  await expect(page.getByRole("region", { name: "Workspace Snapshot" })).toBeVisible();
  await expect(page).toHaveScreenshot("source-workspace.png");
});

test("metadata editor", async ({ page }) => {
  await openWorkspacePage(page, "Metadata");
  await expect(page.locator('input[value="climate-model-lab"]')).toBeVisible();
  await expect(page).toHaveScreenshot("metadata.png");
});

test("hardware bill of materials", async ({ page }) => {
  await openWorkspacePage(page, "Hardware");
  await expect(page.locator('input[value="Intel Xeon Gold 6338"]')).toBeVisible();
  await expect(page).toHaveScreenshot("hardware-bom.png");
});

test("reproducibility readiness", async ({ page }) => {
  await openWorkspacePage(page, "Reproducibility Readiness");
  await expect(page.getByText("Base image tag is mutable")).toBeVisible();
  await expect(page).toHaveScreenshot("evaluate-complete.png");
});

test("build runtime", async ({ page }) => {
  await openWorkspacePage(page, "Build");
  await expect(page.getByText("Build Runtime", { exact: true })).toBeVisible();
  await expect(page).toHaveScreenshot("build-runtime.png");
});

test("software bill of materials", async ({ page }) => {
  await openWorkspacePage(page, "SBOM");
  await expect(page.getByText("Generate SBOM", { exact: true })).toBeVisible();
  await expect(page).toHaveScreenshot("sbom.png");
});

test("activation", async ({ page }) => {
  await openWorkspacePage(page, "Activation");
  await expect(page.getByRole("heading", { name: "Test Activation" })).toBeVisible();
  await expect(page).toHaveScreenshot("activation.png");
});

test("experiments", async ({ page }) => {
  await openWorkspacePage(page, "Experiments");
  await expect(page.getByRole("button", { name: "EXP-001 regional-forecast" })).toBeVisible();
  await expect(page).toHaveScreenshot("experiments.png");
});

test("archive", async ({ page }) => {
  await openWorkspacePage(page, "Archive");
  await expect(page.getByText("Deposit & Share", { exact: true })).toBeVisible();
  await expect(page).toHaveScreenshot("archive.png");
});

test("seal readiness", async ({ page }) => {
  await openWorkspacePage(page, "Seal");
  await expect(page.getByRole("button", { name: "Seal anyway" })).toBeVisible();
  await expect(page).toHaveScreenshot("seal-ready.png");
});
