import path from "node:path";
import { expect, test } from "@playwright/test";
import { openPort } from "../../e2e/helpers/flow";
import { createDemoKit } from "../helpers/demo";

const { demoStep, clickDemo } = createDemoKit({
  stepDelayMs: 250,
  narrationDelayMs: 650,
});

// Focused upload-only demo: it provisions a workbench, opens the Source shell,
// and uploads Code Ocean capsule 7784598, stopping once the archive is
// extracted into the workspace. Deliberately does NOT author metadata, build a
// runtime, or run experiments — it exists to exercise (and visualize) the
// large-capsule upload path in isolation.

const CAPSULE_ARCHIVE = "capsule-7784598.zip";

test("upload Code Ocean capsule 7784598", async ({ page }) => {
  test.setTimeout(900000);

  const sourceArchive = path.resolve(
    __dirname,
    `../../../../examples/code-ocean/${CAPSULE_ARCHIVE}`,
  );
  const sourcePanel = page.getByRole("region", { name: "Source Acquisition" });

  await demoStep(page, "Open REE creation flow", async () => {
    await page.goto("/");
    await clickDemo(page, page.getByRole("button", { name: "Create REE" }), "Start REE creation");
    await expect(page.getByRole("heading", { name: "Choose a lab location" })).toBeVisible();
    await clickDemo(
      page,
      page.getByRole("button", { name: /connected/ }).first(),
      "Choose the lab location — the agent that will host this REE's workbench",
    );
    await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
  });

  await demoStep(page, "Provision workbench", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Provision workbench/i }),
      "Provision the workbench",
    );
    await expect(
      page.getByRole("navigation").getByRole("button", { name: "Source", exact: true }),
    ).toBeVisible();
    await openPort(page, "Source");
    await expect(sourcePanel).toBeVisible();
  });

  await demoStep(page, "Upload Code Ocean capsule", async () => {
    // Drive the upload with page-level locators (not the region) and click
    // "Add to workspace" before asserting, rather than gating the step on the
    // post-commit "Replace" control.
    await clickDemo(page, page.getByRole("button", { name: "Upload tarball" }));
    await page
      .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
      .setInputFiles(sourceArchive);
    await clickDemo(
      page,
      page.getByRole("button", { name: /Add to workspace/i }),
      `Extract ${CAPSULE_ARCHIVE} into the REE workspace`,
    );
    await expect(page.getByText(CAPSULE_ARCHIVE, { exact: true }).first()).toBeVisible({
      timeout: 60000,
    });
  });

  // NOTE: intentionally no "Expand files" step here. The upload itself completes
  // fine server-side; what hangs for this capsule is rendering its extracted file
  // browser — a 128-node, depth-7 tree (mostly nested .vscode junk under code/) —
  // under always-on video recording. Keep this demo upload-only until that
  // file-browser render is made resilient to large/deep trees.

  await demoStep(page, "Release workbench", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await page.getByRole("button", { name: /Expand workbench console/i }).click();
    const releaseButton = page.getByRole("button", { name: /Release workbench/i }).first();
    await expect(releaseButton).toBeVisible();
    await clickDemo(page, releaseButton, "Release the workbench container");
    await expect(page).toHaveURL("/");
  });
});
