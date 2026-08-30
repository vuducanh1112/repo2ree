import path from "node:path";
import { expect, test } from "@playwright/test";
import { openFilesConsole, openPort, openWorkbenchConsole } from "../../e2e/helpers/flow";
import { createDemoKit } from "../helpers/demo";

const { demoStep, clickDemo, showcasePanel } = createDemoKit({
  stepDelayMs: 250,
  narrationDelayMs: 650,
});

// Focused upload-only demo: it provisions a workbench, opens the Source shell,
// and uploads Code Ocean capsule 4825344, stopping once the archive is
// extracted into the workspace. Deliberately does NOT author metadata, build a
// runtime, or run experiments — it exists to exercise (and visualize) the
// large-capsule upload path in isolation.

const CAPSULE_ARCHIVE = "capsule-4825344.zip";

test("upload Code Ocean capsule 4825344", async ({ page }) => {
  test.setTimeout(900000);

  const sourceArchive = path.resolve(
    __dirname,
    `../../../../examples/code-ocean/${CAPSULE_ARCHIVE}`,
  );
  const sourcePanel = page.getByRole("region", { name: "Source Acquisition" });

  await demoStep(page, "Choose a lab and bring the bench online", async () => {
    await page.goto("/");
    await clickDemo(
      page,
      page.getByRole("button", { name: "Create a new REE" }),
      "Start REE creation",
    );
    await expect(page.getByRole("heading", { name: "Where should this REE run?" })).toBeVisible();
    await clickDemo(
      page,
      page.getByRole("button", { name: /connected/ }).first(),
      "Pick the lab — the machine that will host this REE's workbench, for its whole life",
    );
    const setup = page.getByRole("region", { name: "Set up the workbench" });
    await expect(setup).toBeVisible();
    await showcasePanel(
      page,
      setup,
      "Choosing a lab opens its bench setup in place — the base image the REE runs on, and whether the bench starts blank or from a downloaded bundle",
    );
    await clickDemo(
      page,
      setup.getByRole("button", { name: /Provision workbench/i }),
      "Provision the workbench",
    );
    await expect(
      page
        .getByRole("navigation", { name: "Workspace pages" })
        .getByRole("button", { name: "Source", exact: true }),
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

  await demoStep(page, "Confirm capsule extracted into workspace", async () => {
    await clickDemo(
      page,
      page
        .getByRole("region", { name: "Workspace status" })
        .getByRole("button", { name: /^Files/ }),
      "Confirm Code Ocean files were extracted at the upstream root",
    );
    await openFilesConsole(page);
    await page.getByPlaceholder("Filter files…").fill("code");
    await expect(page.getByRole("button", { name: /run/i }).first()).toBeVisible();
  });

  await demoStep(page, "Release workbench", async () => {
    await clickDemo(
      page,
      page
        .getByRole("region", { name: "Workbench status" })
        .getByRole("button", { name: /^Workbench/ }),
      "Open the workbench console from the footer status bar",
    );
    await openWorkbenchConsole(page);
    const releaseButton = page.getByRole("button", { name: /Release workbench/i }).first();
    await expect(releaseButton).toBeVisible();
    await clickDemo(page, releaseButton, "Release the workbench container");
    await expect(page).toHaveURL("/");
  });
});
