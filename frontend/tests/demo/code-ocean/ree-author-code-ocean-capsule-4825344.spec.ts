import path from "node:path";
import { expect, type Locator, type Page, test } from "@playwright/test";
import { stepShot } from "../../screenshot";

// Focused upload-only demo: it provisions a workbench, opens the Source shell,
// and uploads Code Ocean capsule 4825344, stopping once the archive is
// extracted into the workspace. Deliberately does NOT author metadata, build a
// runtime, or run experiments — it exists to exercise (and visualize) the
// large-capsule upload path in isolation.

const DEMO_STEP_DELAY_MS = 250;
const DEMO_NARRATION_DELAY_MS = 650;

const CAPSULE_ARCHIVE = "capsule-4825344.zip";

async function demoStep(page: Page, name: string, body: () => Promise<void>) {
  await stepShot(page, name, "before");
  await test.step(name, body);
  await stepShot(page, name, "after");
}

async function showDemoFocus(locator: Locator, narration?: string) {
  await locator.evaluate((el, text) => {
    const containerId = "__ree_demo_focus_container__";
    const boxId = "__ree_demo_focus_box__";
    const labelId = "__ree_demo_focus_label__";

    let container = document.getElementById(containerId);
    if (!container) {
      container = document.createElement("div");
      container.id = containerId;
      Object.assign(container.style, {
        position: "fixed",
        left: "0",
        top: "0",
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: "2147483647",
      });
      document.body.appendChild(container);
    }

    let box = document.getElementById(boxId);
    if (!box) {
      box = document.createElement("div");
      box.id = boxId;
      Object.assign(box.style, {
        position: "fixed",
        border: "2px solid #ffc700",
        borderRadius: "10px",
        boxShadow: "0 0 0 3px rgba(255, 199, 0, 0.18)",
        boxSizing: "border-box",
        pointerEvents: "none",
      });
      container.appendChild(box);
    }

    let label = document.getElementById(labelId);
    if (!label) {
      label = document.createElement("div");
      label.id = labelId;
      Object.assign(label.style, {
        position: "fixed",
        background: "rgba(0, 0, 0, 0.88)",
        color: "#fff",
        padding: "6px 9px",
        borderRadius: "7px",
        font: "600 12px/1.35 ui-sans-serif, system-ui, sans-serif",
        boxShadow: "0 6px 20px rgba(0,0,0,0.32)",
        pointerEvents: "none",
        maxWidth: "360px",
        whiteSpace: "normal",
      });
      container.appendChild(label);
    }

    const rect = el.getBoundingClientRect();
    const pad = 6;
    const left = Math.max(6, rect.left - pad);
    const top = Math.max(6, rect.top - pad);
    const width = Math.max(24, rect.width + pad * 2);
    const height = Math.max(24, rect.height + pad * 2);

    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
    box.style.width = `${width}px`;
    box.style.height = `${height}px`;
    box.style.display = "block";

    if (text) {
      label.textContent = text;
      label.style.display = "block";
      label.style.left = `${left}px`;
      label.style.top = `${Math.max(6, top - 36)}px`;
    } else {
      label.style.display = "none";
    }
  }, narration);
}

async function clickDemo(page: Page, locator: Locator, narration?: string) {
  const target = locator.first();
  await expect(target).toBeVisible({ timeout: 10000 });
  await target.scrollIntoViewIfNeeded();
  await showDemoFocus(target, narration);
  if (narration) await page.waitForTimeout(DEMO_NARRATION_DELAY_MS);
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
  await target.click();
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
}

async function openPort(page: Page, label: string) {
  await page.keyboard.press("Escape").catch(() => {});
  await page.getByRole("navigation").getByRole("button", { name: label, exact: true }).click();
}

test("upload Code Ocean capsule 4825344", async ({ page }) => {
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
    await clickDemo(
      page,
      page.getByRole("button", { name: "Decompose" }),
      "Decompose so the source shell is visible on its own",
    );
    await expect(page.getByRole("button", { name: "Reassemble" })).toBeVisible();
    await openPort(page, "Source");
    await expect(sourcePanel).toBeVisible();
  });

  await demoStep(page, "Upload Code Ocean capsule", async () => {
    // Mirror the previously-working flow: drive the upload with page-level
    // locators (not the region) and click "Add to workspace" before asserting,
    // rather than gating the step on the post-commit "Replace" control.
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
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("button", { name: "Expand files" }),
      "Confirm Code Ocean files were extracted at workspace root",
    );
    await page.getByPlaceholder("Filter files…").fill("code");
    await expect(page.getByRole("button", { name: /run/i }).first()).toBeVisible();
  });

  await demoStep(page, "Release workbench", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await page.getByRole("button", { name: /Expand workbench console/i }).click();
    const releaseButton = page.getByRole("button", { name: /Release workbench/i }).first();
    await expect(releaseButton).toBeVisible();
    await clickDemo(page, releaseButton, "Release the workbench container");
    await expect(page).toHaveURL("/");
  });
});
