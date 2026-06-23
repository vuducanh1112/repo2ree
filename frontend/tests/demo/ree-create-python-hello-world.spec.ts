import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, type Locator, type Page, test } from "@playwright/test";
import { stepShot } from "../screenshot";

const DEMO_STEP_DELAY_MS = 350;
const DEMO_NARRATION_DELAY_MS = 900;

/**
 * A demo step: runs the body inside a named `test.step` (so the trace/report
 * groups its actions) and captures a named, ordered screenshot once the step's
 * UI has settled.
 */
async function demoStep(page: Page, name: string, body: () => Promise<void>) {
  await stepShot(page, name, "before");
  await test.step(name, body);
  await stepShot(page, name, "after");
}

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
  // DinD: every workbench builds against a cold (empty) image cache, so the
  // build/activation/experiment steps are full cold pulls + installs. Combined
  // with the narration delays this needs a much larger budget than warm runs.
  test.setTimeout(420000);

  const sourceArchive = path.resolve(__dirname, "../resources/examples/python-hello-world.tar.gz");
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
  const main = page.getByRole("main");
  // Source acquisition is now a floating hub panel (role=region), not a docked
  // page; its Clear-source action lives in that panel's header.
  const sourcePanel = page.getByRole("region", { name: "Source Acquisition" });
  const clearSourceButton = sourcePanel.getByRole("button", { name: /Clear source/i });

  await demoStep(page, "Open REE creation flow", async () => {
    await page.goto("/");
    await clickDemo(page, page.getByRole("button", { name: "Create REE" }), "Start REE creation");
    await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
  });

  await demoStep(page, "Provision workbench", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: /Provision workbench/i }),
      "Provision the workbench",
    );
    // Provisioning lands on the canvas hub; decompose before source acquisition
    // so the whole authoring walkthrough happens against the shell view.
    await expect(
      page.getByRole("navigation").getByRole("button", { name: "Source", exact: true }),
    ).toBeVisible();
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("button", { name: "Decompose" }),
      "Decompose the pod before adding source, so each shell stays visible while authoring",
    );
    await expect(page.getByRole("button", { name: "Reassemble" })).toBeVisible();
    await page.waitForTimeout(800);
    await page.getByRole("navigation").getByRole("button", { name: "Source", exact: true }).click();
    await expect(
      page.getByRole("region", { name: "Source Acquisition" }).getByText("Source Acquisition", {
        exact: true,
      }),
    ).toBeVisible();
  });

  await demoStep(page, "Upload source archive", async () => {
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

  await demoStep(page, "Review workspace source", async () => {
    await expect(clearSourceButton).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    // Shown in both the committed Source Snapshot field and the Workspace
    // Snapshot metadata Name, so match the first occurrence.
    await expect(
      page.getByText("python-hello-world.tar.gz", { exact: true }).first(),
    ).toBeVisible();
    const snapshot = page.getByText("Workspace Snapshot").locator("..");
    await expect(snapshot.getByText("Upload", { exact: true })).toBeVisible();
  });

  await demoStep(page, "Browse extracted files", async () => {
    // Files live in the file-tree HUD console docked on the canvas; leave the
    // source dock and expand it.
    await page.keyboard.press("Escape");
    await clickDemo(
      page,
      page.getByRole("button", { name: "Expand files" }),
      "Browse workspace files in the docked file console",
    );

    await expect(page.getByRole("button", { name: "Collapse files" })).toBeVisible();
    await page.getByPlaceholder("Filter files…").fill("workspace");
    for (const nodeName of archiveNodeNames) {
      const escapedNodeName = nodeName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      await expect(page.getByRole("button", { name: new RegExp(escapedNodeName) })).toBeVisible();
    }
    await clickDemo(
      page,
      page.getByRole("button", { name: /main\.py/i }).first(),
      "Inspect the uploaded files. Here: workspace/python_hello_world/main.py",
    );
    await page.waitForTimeout(1000);
    await showcaseScroll(page, 700);
    await showcaseScroll(page, -700);
  });

  await demoStep(page, "Provide metadata", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "Metadata", exact: true }),
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

  await demoStep(page, "Provide HBOM entry", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "Hardware", exact: true }),
      "Add a hardware bill of materials entry",
    );
    await expect(main.getByText("Hardware BOM", { exact: true })).toBeVisible();
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

  await demoStep(page, "Evaluate REE", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page
        .getByRole("navigation")
        .getByRole("button", { name: "Reproducibility Readiness", exact: true }),
      "Evaluate the projects risks to reproducibility, by analyzing declared dependencies",
    );
    await expect(main.getByText("Reproducibility Readiness", { exact: true })).toBeVisible();
    await clickDemo(
      page,
      main.getByRole("button", { name: /^Run Evaluate$/ }),
      "Run evaluation to obtain reproducibility score",
    );
    await expect(main.getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible({
      timeout: 60000,
    });
    await showcasePanel(page, main.getByText("Run Log").first(), "Review output logs");
  });

  await demoStep(page, "Build runtime", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "Build", exact: true }),
      "Build runtime artifact",
    );
    await expect(main.getByText("Build Runtime", { exact: true })).toBeVisible();
    await fillDemo(
      page,
      page.getByPlaceholder("Pick a .sh file from the workspace"),
      "python_hello_world/build_runtime.sh",
      "Select the active build script",
    );
    await clickDemo(page, main.getByRole("button", { name: /Run build/ }), "Run runtime build");
    // Dwell on the build log while it streams live (the cold DinD build runs
    // for ~30s, so there is plenty to show). The panel tails new lines itself.
    await showcasePanel(
      page,
      main.getByText(/Build log/i).first(),
      "Watch the build log stream live",
    );
    await page.waitForTimeout(5000);
    await expect(main.getByRole("button", { name: /Re-build/ })).toBeVisible({ timeout: 90000 });
  });

  await demoStep(page, "Configure runtime environment", async () => {
    // The produced runtime artifact and its substrate now live on the inner
    // shell — the Runtime Environment page — reached from the already
    // decomposed pod by clicking the inner-shell pod.
    await page.keyboard.press("Escape").catch(() => {});
    await expect(page.getByRole("button", { name: "Reassemble" })).toBeVisible();
    await clickDemo(
      page,
      page.getByRole("button", { name: "Open runtime environment" }),
      "Open the inner shell: the runtime the whole REE executes on",
    );
    await expect(main.getByText("Runtime Environment", { exact: true })).toBeVisible();
    await clickDemo(
      page,
      page.getByPlaceholder("runtime.tar.gz").locator("..").getByTitle("Browse repository files"),
      "Open runtime file picker",
    );
    await expect(page.getByRole("button", { name: "python_hello_world/runtime.tar" })).toBeVisible({
      timeout: 30000,
    });
    await clickDemo(
      page,
      page.getByRole("button", { name: "python_hello_world/runtime.tar" }),
      "Select produced runtime file",
    );
    await showcasePanel(
      page,
      main.getByText("Runtime Substrate", { exact: true }),
      "Choose how the workbench enters the runtime — shared by activation and every experiment",
    );
  });

  await demoStep(page, "Generate SBOM", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "SBOM", exact: true }),
      "Open SBOM page",
    );
    const sbomPanel = page.getByRole("region", { name: "Generate SBOM" });
    await clickDemo(page, sbomPanel.getByRole("button", { name: /^Generate$/ }), "Run SBOM scan");
    await expect(sbomPanel.getByRole("button", { name: /^Regenerate$/ })).toBeVisible({
      timeout: 60000,
    });
    await expect(sbomPanel.getByText("SBOM ready", { exact: true }).first()).toBeVisible({
      timeout: 60000,
    });
    await showcasePanel(page, sbomPanel.getByText(/SBOM log/i).first(), "Review SBOM logs");
  });

  //console.log("SBOM generated, proceeding to activation test...");

  await demoStep(page, "Test activation", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "Activation", exact: true }),
      "Open activation test",
    );
    await expect(main.getByText("Activation Command", { exact: true })).toBeVisible();
    await fillDemo(
      page,
      main.getByPlaceholder(/e\.g\. python/).first(),
      "python -c \"import sys; print('ok')\"",
      "Enter activation command",
    );
    await clickDemo(
      page,
      main.getByRole("button", { name: /Run activation/ }),
      "Execute activation",
    );
    await expect(main.getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 90000 });
    await showcasePanel(page, main.getByText(/Activation log/i).first(), "Review activation logs");
  });

  await demoStep(page, "Run experiment", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("button", { name: "Open experiments" }),
      "Open the core experiment catalog from the decomposed view",
    );
    await expect(main.getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();
    await clickDemo(
      page,
      main.getByRole("button", { name: /Add experiment/i }).first(),
      "Add a new experiment",
    );
    await fillDemo(page, main.getByPlaceholder("smoke-test"), "echo-hello", "Name the experiment");
    await fillDemo(
      page,
      main.getByPlaceholder("pytest tests/smoke -q"),
      "echo hello",
      "Set the command to echo hello",
    );
    const outputsCard = main
      .locator("div")
      .filter({ hasText: /^Expected outputs/ })
      .first();
    await clickDemo(
      page,
      outputsCard.getByRole("button", { name: /Add/ }).first(),
      "Declare an expected output",
    );
    await fillDemo(
      page,
      main.getByPlaceholder("PASSED").first(),
      "hello",
      "Require stdout to contain 'hello'",
    );
    await clickDemo(page, main.getByRole("button", { name: /^Run$/ }), "Run the experiment");
    await page.waitForTimeout(5000);
    await showcaseScroll(page, 800);
    await showcaseScroll(page, 800);
    await page.waitForTimeout(5000);
    const runResultPanel = main
      .locator("div")
      .filter({ hasText: /^Run result/ })
      .first();
    await expect(runResultPanel.getByText("pass", { exact: true })).toBeVisible({ timeout: 90000 });
  });

  await demoStep(page, "Review decomposed experiment view", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await expect(page.getByRole("button", { name: "Reassemble" })).toBeVisible();
    await showcasePanel(
      page,
      page.getByRole("button", { name: "echo-hello" }),
      "The core shell now carries the experiment as its own cabled panel",
    );
    await page.waitForTimeout(1500);
  });

  await demoStep(page, "Seal and download", async () => {
    await clickDemo(
      page,
      page.getByRole("button", { name: "Reassemble" }),
      "Reassemble the pod before sealing",
    );
    await expect(page.getByRole("button", { name: "Decompose" })).toBeVisible();
    await page.waitForTimeout(800);
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "Seal", exact: true }),
      "Seal the REE package",
    );
    // The seal panel is pinned inside the constellation hub, not the docked main.
    const sealPanel = page.getByRole("region", { name: "Seal" });
    // The seal panel now shows source/runtime bundle toggles inline before sealing.
    await expect(sealPanel.getByText("Bundle contents", { exact: true })).toBeVisible();

    await clickDemo(
      page,
      sealPanel.getByRole("button", { name: /Seal (REE|anyway)/ }),
      "Seal — locks the REE with the chosen bundle contents",
    );
    // Sealing is a heavy synchronous round-trip (the backend assembles the
    // bundle twice — a digest pre-pass plus the final stamped build — then
    // re-enumerates the workspace), so allow the same budget as the other
    // backend-bound steps rather than the tighter 20s that flaked under load.
    await expect(sealPanel.getByText("REE SEALED", { exact: true })).toBeVisible({
      timeout: 60000,
    });

    // The Download REE button lives in the app header once the REE is sealed.
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      clickDemo(
        page,
        page.getByRole("banner").getByRole("button", { name: /Download REE/ }),
        "Download the sealed REE archive",
      ),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.zip$/i);
  });

  await demoStep(page, "Release workbench", async () => {
    // The release button lives in the bench console HUD; open it first.
    await page.keyboard.press("Escape").catch(() => {});
    await page.getByRole("button", { name: /Expand workbench console/i }).click();
    const releaseButton = page.getByRole("button", { name: /Release workbench/i }).first();
    await expect(releaseButton).toBeVisible();
    await clickDemo(page, releaseButton, "Release the workbench container");
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("button", { name: /Create REE/i })).toBeVisible();
  });
});
