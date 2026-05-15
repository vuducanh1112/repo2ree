import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, type Locator, type Page, test } from "@playwright/test";

const DEMO_STEP_DELAY_MS = 350;
const DEMO_NARRATION_DELAY_MS = 900;

async function showDemoFocus(locator: Locator, narration?: string) {
  await locator.evaluate((el, text) => {
    const containerId = "__ree_demo_focus_container__";
    const boxId = "__ree_demo_focus_box__";
    const pulseId = "__ree_demo_focus_pulse__";
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

      const style = document.createElement("style");
      style.id = "__ree_demo_focus_style__";
      style.textContent = `
				@keyframes reeDemoPulse {
					0% { transform: scale(1); opacity: 0.55; }
					70% { transform: scale(1.08); opacity: 0.18; }
					100% { transform: scale(1.16); opacity: 0; }
				}
			`;
      document.head.appendChild(style);
    }

    let pulse = document.getElementById(pulseId);
    if (!pulse) {
      pulse = document.createElement("div");
      pulse.id = pulseId;
      Object.assign(pulse.style, {
        position: "fixed",
        border: "2px solid rgba(255, 199, 0, 0.95)",
        borderRadius: "10px",
        boxSizing: "border-box",
        pointerEvents: "none",
        animation: "reeDemoPulse 1.1s ease-out infinite",
      });
      container.appendChild(pulse);
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
        maxWidth: "320px",
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

    for (const element of [pulse, box]) {
      element.style.left = `${left}px`;
      element.style.top = `${top}px`;
      element.style.width = `${width}px`;
      element.style.height = `${height}px`;
      element.style.display = "block";
    }

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
  await locator.scrollIntoViewIfNeeded();
  await showDemoFocus(locator, narration);
  if (narration) {
    await page.waitForTimeout(DEMO_NARRATION_DELAY_MS);
  }
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
  await locator.click();
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
}

async function fillDemo(page: Page, locator: Locator, value: string, narration?: string) {
  await locator.scrollIntoViewIfNeeded();
  await showDemoFocus(locator, narration);
  if (narration) {
    await page.waitForTimeout(DEMO_NARRATION_DELAY_MS);
  }
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
  await locator.fill(value);
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
}

async function showcaseScroll(page: Page, deltaY = 700) {
  await page.mouse.wheel(0, deltaY);
  await page.waitForTimeout(700);
}

async function showcasePanel(page: Page, locator: Locator, narration: string) {
  await expect(locator).toBeVisible({ timeout: 10000 });
  await locator.scrollIntoViewIfNeeded();
  await showDemoFocus(locator, narration);
  await page.waitForTimeout(1200);
}

test("upload source archive into workspace", async ({ page }) => {
  test.setTimeout(180000);

  const expectOverviewCableActive = async (label: string) => {
    await expect(page.getByText(`✓ ${label}`, { exact: true })).toBeVisible();
  };

  const sourceArchive = path.resolve(__dirname, "resources/examples/python-hello-world.tar.gz");
  const archiveEntries = execFileSync("tar", ["-tzf", sourceArchive], { encoding: "utf8" })
    .split("\n")
    .map((entry) => entry.trim())
    .filter(Boolean);
  const archiveNodeNames = [
    ...new Set(
      archiveEntries
        .map((entry) => entry.replace(/\/+$/, "").split("/").filter(Boolean).pop())
        .filter((name): name is string => Boolean(name)),
    ),
  ];
  const step3WorkspaceActions = page
    .locator("div")
    .filter({ hasText: "Workspace Snapshot" })
    .filter({ hasText: /Browse workspace files/ })
    .first();
  const main = page.getByRole("main");

  await test.step("Open REE creation flow", async () => {
    await page.goto("/");
    await clickDemo(page, page.getByRole("button", { name: "Create REE" }), "Start REE creation");
    await expect(
      page.getByRole("main").getByText("Source Acquisition", { exact: true }),
    ).toBeVisible();
  });

  await test.step("Upload source archive", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: "Upload tarball" }),
      "Upload tarball source",
    );
    await page
      .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
      .setInputFiles(sourceArchive);
    await clickDemo(
      page,
      page.getByRole("button", { name: /Add to workspace/i }),
      "Add source to workspace",
    );
  });

  await test.step("Review workspace source", async () => {
    await expect(step3WorkspaceActions).toBeVisible();
    await expect(
      step3WorkspaceActions.getByRole("button", { name: /Clear workspace source/i }),
    ).toBeVisible();
    await expect(
      step3WorkspaceActions.getByRole("button", { name: /Browse workspace files/i }),
    ).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    await expect(page.getByText("python-hello-world.tar.gz", { exact: true })).toBeVisible();
  });

  await test.step("Browse extracted files", async () => {
    await clickDemo(
      page,
      step3WorkspaceActions.getByRole("button", { name: /Browse workspace files/i }),
      "Browse workspace files",
    );

    await expect(main.getByText("Files", { exact: true })).toBeVisible();
    await expect(page.getByText("Workspace", { exact: true })).toBeVisible();
    for (const nodeName of archiveNodeNames) {
      const escapedNodeName = nodeName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      await expect(page.getByRole("button", { name: new RegExp(escapedNodeName) })).toBeVisible();
    }
    await clickDemo(
      page,
      page.getByRole("button", { name: /main\.py/i }).first(),
      "Inspect the uploaded files. Here: python_hello_world/main.py",
    );
    await page.waitForTimeout(1000);
    await showcaseScroll(page, 700);
    await showcaseScroll(page, -700);
  });

  await test.step("Provide metadata", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Provide Metadata.*project identity metadata/i }),
      "Provide project metadata",
    );
    await expect(main.getByRole("heading", { name: "Metadata", exact: true })).toBeVisible();
    await fillDemo(
      page,
      page.getByPlaceholder("deepfold-protein-structure-prediction"),
      "ree-hello-world",
      "Change REE name",
    );
    await expect(page.getByPlaceholder("deepfold-protein-structure-prediction")).toHaveValue(
      "ree-hello-world",
    );
    await fillDemo(page, page.getByPlaceholder("1.0.0"), "1.0.0", "Set REE version");
    await expect(page.getByPlaceholder("1.0.0")).toHaveValue("1.0.0");
    await fillDemo(
      page,
      page.getByPlaceholder("REE for reproducible execution of..."),
      "A reusable execution environment for the Python hello world archive.",
      "Describe the REE",
    );
    await expect(page.getByPlaceholder("REE for reproducible execution of...")).toHaveValue(
      "A reusable execution environment for the Python hello world archive.",
    );
  });

  await test.step("Provide HBOM entry", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Create HBOM.*Enter hardware bill of materials/ }),
      "Add a hardware bill of materials entry",
    );
    await expect(main.getByText("Create Hardware BOM", { exact: true })).toBeVisible();
    await clickDemo(
      page,
      main.locator("button").filter({ hasText: "Add CPU" }).first(),
      "Create a CPU component card",
    );
    await fillDemo(
      page,
      main.getByPlaceholder("Intel Core i9-14900K").first(),
      "Intel Core i9-14900K",
      "Enter the CPU device model",
    );
    await expect(main.getByPlaceholder("Intel Core i9-14900K").first()).toHaveValue(
      "Intel Core i9-14900K",
    );
  });

  await test.step("Evaluate REE", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Evaluate.*Score reproducibility level/ }),
      "Evaluate the projects risks to reproducibility, by analyzing declared dependencies",
    );
    await expect(main.getByText("Evaluate", { exact: true })).toBeVisible();
    await clickDemo(
      page,
      main.getByRole("button", { name: /^Play Run Evaluate$/ }),
      "Run evaluation to obtain reproducibility score",
    );
    await expect(main.getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible({
      timeout: 20000,
    });
    await showcasePanel(
      page,
      main.getByText("Run Log", { exact: true }).first(),
      "Review output logs",
    );
    await expectOverviewCableActive("Evaluate");
  });

  await test.step("Build runtime", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Build Runtime.*Build the runtime tarball/ }),
      "Build runtime artifact",
    );
    await expect(main.getByText("Build Runtime", { exact: true })).toBeVisible();
    await fillDemo(
      page,
      page.getByPlaceholder("build_runtime.sh"),
      "python_hello_world/build_runtime.sh",
      "Provide build script path",
    );
    await clickDemo(page, main.getByRole("button", { name: /Run build/ }), "Run runtime build");
    await expect(main.getByRole("button", { name: /Re-build/ })).toBeVisible({ timeout: 20000 });
    await showcasePanel(
      page,
      main.getByText("Output", { exact: true }).first(),
      "Review build logs",
    );
    await clickDemo(
      page,
      page.getByPlaceholder("runtime.tar.gz").locator("..").getByTitle("Browse repository files"),
      "Open runtime file picker",
    );
    await expect(page.getByRole("button", { name: "python_hello_world/runtime.tar" })).toBeVisible({
      timeout: 20000,
    });
    await clickDemo(
      page,
      page.getByRole("button", { name: "python_hello_world/runtime.tar" }),
      "Select produced runtime file",
    );
    await clickDemo(
      page,
      main.locator('button[aria-label="Toggle runtime included"]'),
      "Mark runtime as included",
    );
    await expectOverviewCableActive("Runtime");
  });

  await test.step("Generate SBOM", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Generate SBOM.*Scan runtime with syft/ }),
      "Generate SBOM",
    );
    await expect(main.getByText("Generate SBOM", { exact: true })).toBeVisible();
    await clickDemo(
      page,
      main.getByRole("button", { name: /^Play Generate SBOM$/ }),
      "Run SBOM scan",
    );
    await expect(main.getByRole("button", { name: /Regenerate SBOM/ })).toBeVisible({
      timeout: 20000,
    });
    await expect(main.getByText("SBOM run succeeded", { exact: true })).toBeVisible({
      timeout: 20000,
    });
    await showcasePanel(
      page,
      main.getByText("Output", { exact: true }).first(),
      "Review SBOM logs",
    );
    await expectOverviewCableActive("SBOM");
  });

  //console.log("SBOM generated, proceeding to activation test...");

  await test.step("Test activation", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Test Activation.*Verify container activates/ }),
      "Run activation test",
    );
    await expect(main.getByText("Test Activation", { exact: true })).toBeVisible();
    await fillDemo(
      page,
      page.getByPlaceholder("activation_test.sh"),
      "python_hello_world/activate_runtime.sh",
      "Provide activation script path",
    );
    await clickDemo(
      page,
      main.getByRole("button", { name: /Run activation/ }),
      "Execute activation",
    );
    await expect(main.getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 20000 });
    await showcasePanel(
      page,
      main.getByText("Output", { exact: true }).first(),
      "Review activation logs",
    );
    await expectOverviewCableActive("Activation");
  });

  await test.step("Seal and download", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Seal.*Seal the REE/ }),
      "Seal the REE package",
    );
    await expect(main.getByText("Seal REE", { exact: true })).toBeVisible();
    await clickDemo(page, main.getByRole("button", { name: /Seal/ }).first(), "Confirm sealing");
    await expect(main.getByText("Seal this REE?", { exact: true })).toBeVisible();
    await clickDemo(page, main.getByRole("button", { name: /Seal (REE|anyway)/ }), "Finalize seal");
    await expect(main.getByText("REE SEALED", { exact: true })).toBeVisible({ timeout: 20000 });
    const sealedDownloadButton = main.getByRole("button", { name: /Download REE/ }).first();
    await expect(sealedDownloadButton).toBeVisible();

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      clickDemo(page, sealedDownloadButton, "Download sealed REE package"),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.zip$/i);
  });
});
