import path from "node:path";
import { expect, type Locator, type Page, test } from "@playwright/test";
import { stepShot } from "../../screenshot";

const DEMO_STEP_DELAY_MS = 250;
const DEMO_NARRATION_DELAY_MS = 650;

const CAPSULE_NAME =
  "A Wireless Bidirectional Neural Interface with Neural-Signal-Dependent Self-Fine-Tuning for Closed-Loop Motor Modulation";
const CAPSULE_DESCRIPTION =
  "Code Ocean capsule for closed-loop motor modulation using neural-signal feedback from beagle gait-recovery experiments.";

const CODEOCEAN_IMAGE = "registry.codeocean.com/published/221e8df3-ad30-441f-9643-8aac03f03dae:v1";

const BUILD_RUNTIME_SCRIPT = `#!/usr/bin/env bash
set -euo pipefail

IMAGE="${CODEOCEAN_IMAGE}"
OUT="runtime.tar.gz"

docker pull --platform linux/amd64 "$IMAGE"
docker save "$IMAGE" -o "$OUT"
ls -lh "$OUT"
`;

// Each runnable now owns its full execution. Code Ocean's absolute /data and
// /results are bind-mounted straight off the workspace, so produced results land
// in the workspace (results/…) where output checks read them on the host.
function codeOceanRunScript(command: string): string {
  return `#!/usr/bin/env sh
set -eu

IMAGE=${JSON.stringify(CODEOCEAN_IMAGE)}
RUNTIME_FILE="runtime.tar.gz"

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker load -i "$RUNTIME_FILE"

mkdir -p data results

docker run --rm --platform linux/amd64 \\
  -v "$(pwd):/workspace" -w /workspace \\
  -v "$(pwd)/data:/data" \\
  -v "$(pwd)/results:/results" \\
  "$IMAGE" \\
  sh -c ${JSON.stringify(command)}
`;
}

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

async function fillDemo(page: Page, locator: Locator, value: string, narration?: string) {
  const target = locator.first();
  await expect(target).toBeVisible({ timeout: 10000 });
  await target.scrollIntoViewIfNeeded();
  await showDemoFocus(target, narration);
  if (narration) await page.waitForTimeout(DEMO_NARRATION_DELAY_MS);
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
  await target.fill(value);
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
}

async function selectDemo(page: Page, locator: Locator, value: string, narration?: string) {
  const target = locator.first();
  await expect(target).toBeVisible({ timeout: 10000 });
  await target.scrollIntoViewIfNeeded();
  await showDemoFocus(target, narration);
  if (narration) await page.waitForTimeout(DEMO_NARRATION_DELAY_MS);
  await target.selectOption(value);
  await page.waitForTimeout(DEMO_STEP_DELAY_MS);
}

async function openPort(page: Page, label: string) {
  await page.keyboard.press("Escape").catch(() => {});
  await page.getByRole("navigation").getByRole("button", { name: label, exact: true }).click();
}

// Save a runnable's run script: fill the RunScriptCard textarea, then click its
// "Save run script" button (shared by activation and experiment editors).
async function saveRunScript(page: Page, textboxName: string, content: string, narration?: string) {
  const main = page.getByRole("main");
  await fillDemo(
    page,
    main.getByRole("textbox", { name: textboxName, exact: true }),
    content,
    narration,
  );
  await clickDemo(page, main.getByRole("button", { name: "Save run script", exact: true }).first());
}

async function addKeyword(page: Page, keyword: string) {
  const main = page.getByRole("main");
  await fillDemo(page, main.getByPlaceholder("Add custom keyword"), keyword);
  await clickDemo(page, main.getByRole("button", { name: "Add keyword" }));
  await expect(main.getByText(keyword, { exact: true })).toBeVisible();
}

async function addContributor(
  page: Page,
  contributor: { id: string; name: string; affiliation: string },
) {
  const main = page.getByRole("main");
  await fillDemo(page, main.getByPlaceholder("Identifier", { exact: true }).last(), contributor.id);
  await fillDemo(page, main.getByPlaceholder("Name *"), contributor.name);
  await fillDemo(
    page,
    main.getByPlaceholder("Affiliation name", { exact: true }).last(),
    contributor.affiliation,
  );
  await clickDemo(page, main.getByRole("button", { name: "Add contributor entity" }));
  await expect(main.getByText(contributor.name, { exact: true })).toBeVisible();
}

async function addFileShaOutput(page: Page, filePath: string) {
  const main = page.getByRole("main");
  const outputsCard = main
    .locator("div")
    .filter({ hasText: /^Expected outputs/ })
    .first();
  await clickDemo(page, outputsCard.getByRole("button", { name: /Add/ }).first());
  const outputSelects = outputsCard.locator("select");
  await selectDemo(page, outputSelects.nth(0), "file", "Capture a result file");
  await fillDemo(page, main.getByPlaceholder("results/output.txt"), filePath);
  await selectDemo(page, outputSelects.nth(1), "sha256", "Snapshot will fill the hash");
}

async function addExperiment(
  page: Page,
  experiment: { name: string; command: string; output: string },
) {
  const main = page.getByRole("main");
  await clickDemo(page, main.getByRole("button", { name: /Add experiment/i }).first());
  await fillDemo(page, main.getByPlaceholder("smoke-test"), experiment.name, "Name the experiment");
  await saveRunScript(
    page,
    "Experiment run script",
    codeOceanRunScript(experiment.command),
    "The experiment owns its full docker run — Code Ocean's /data and /results mount straight off the workspace",
  );
  await addFileShaOutput(page, experiment.output);
  await clickDemo(page, main.getByRole("button", { name: /Save & back to catalog/ }));
  await expect(main.getByRole("button", { name: experiment.name })).toBeVisible();
}

test("author Code Ocean capsule 7784598 inputs", async ({ page }) => {
  test.setTimeout(900000);

  const sourceArchive = path.resolve(
    __dirname,
    "../../../../examples/code-ocean/capsule-7784598.zip",
  );
  const main = page.getByRole("main");
  const sourcePanel = page.getByRole("region", { name: "Source Acquisition" });

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
    await expect(
      page.getByRole("navigation").getByRole("button", { name: "Source", exact: true }),
    ).toBeVisible();
    await clickDemo(
      page,
      page.getByRole("button", { name: "Decompose" }),
      "Decompose so source, runtime, and experiments are visible as separate shells",
    );
    await expect(page.getByRole("button", { name: "Reassemble" })).toBeVisible();
    await openPort(page, "Source");
    await expect(sourcePanel).toBeVisible();
  });

  await demoStep(page, "Upload Code Ocean capsule", async () => {
    // Drive the upload with page-level locators and click "Add to workspace"
    // before asserting, rather than gating the step on the post-commit
    // "Replace" control (which leaves the step hanging until commit resolves).
    await clickDemo(page, page.getByRole("button", { name: "Upload tarball" }));
    await page
      .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
      .setInputFiles(sourceArchive);
    await clickDemo(
      page,
      page.getByRole("button", { name: /Add to workspace/i }),
      "Extract capsule-7784598.zip into the REE workspace",
    );
    await expect(page.getByText("capsule-7784598.zip", { exact: true }).first()).toBeVisible({
      timeout: 60000,
    });
  });

  await demoStep(page, "Review extracted capsule shape", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("button", { name: "Expand files" }),
      "Confirm Code Ocean files were extracted at workspace root",
    );
    await page.getByPlaceholder("Filter files…").fill("code");
    await expect(page.getByRole("button", { name: /run/i }).first()).toBeVisible();
    await page.getByPlaceholder("Filter files…").fill("Expdata_info");
    await expect(page.getByRole("button", { name: /Expdata_info\.xlsx/i }).first()).toBeVisible();
  });

  await demoStep(page, "Fill capsule metadata", async () => {
    await openPort(page, "Metadata");
    await expect(main.getByRole("heading", { name: "Metadata", exact: true })).toBeVisible();
    await fillDemo(
      page,
      main.getByPlaceholder("deepfold-protein-structure-prediction"),
      CAPSULE_NAME,
      "Use the publication/capsule title as the REE name",
    );
    await fillDemo(page, main.getByPlaceholder("1.0.0"), "1.0.0", "Set REE version");
    await fillDemo(
      page,
      main.getByPlaceholder("REE for reproducible execution of..."),
      CAPSULE_DESCRIPTION,
      "Summarize what the capsule reproduces",
    );
    for (const keyword of [
      "closed-loop motor modulation",
      "biomedical engineering",
      "neural signal feedback",
      "spinal cord stimulation",
    ]) {
      await addKeyword(page, keyword);
    }
    await addContributor(page, {
      id: "ziyao-zhao",
      name: "Ziyao Zhao",
      affiliation: "Tsinghua University",
    });
  });

  await demoStep(page, "Create the build script", async () => {
    await openPort(page, "Build");
    await expect(main.getByText("Build Runtime", { exact: true })).toBeVisible();
    await fillDemo(
      page,
      main.getByLabel("Build script"),
      BUILD_RUNTIME_SCRIPT,
      "Author the image pull and export in REE’s canonical build script",
    );
    await clickDemo(page, main.getByRole("button", { name: "Save build script" }));
  });

  await demoStep(page, "Run runtime build", async () => {
    await clickDemo(
      page,
      main.getByRole("button", { name: "Run build" }),
      "Pull the Code Ocean image and export it as runtime.tar.gz",
    );
    await expect(main.getByText("Built", { exact: true }).first()).toBeVisible({
      timeout: 12 * 60 * 1000,
    });
    await showDemoFocus(
      main.getByText(/Build log/i).first(),
      "Inspect the build log for the docker pull and exported runtime archive",
    );
    await page.waitForTimeout(1400);
  });

  await demoStep(page, "Author activation run script", async () => {
    await openPort(page, "Activation");
    await expect(main.getByText("Activation Run Script", { exact: true })).toBeVisible();
    await saveRunScript(
      page,
      "Activation run script",
      codeOceanRunScript(
        "cd code && python -c \"import numpy, pandas, matplotlib, openpyxl; from pathlib import Path; assert Path('/data/Expdata_info.xlsx').is_file(); assert Path('/results').is_dir(); print('activation ok')\"",
      ),
      "Activation owns its docker run — Code Ocean's linux/amd64 platform and /data, /results mounts live right in the script",
    );
  });

  await demoStep(page, "Author reproducibility experiments", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("button", { name: "Open experiments" }),
      "Open the experiment catalog",
    );
    await expect(main.getByRole("heading", { name: "Experiments", exact: true })).toBeVisible();
    await addExperiment(page, {
      name: "previous modulation day 0",
      command: "cd code && bash run",
      output: "results/Day0_Exp0/stimulation_results.csv",
    });
    await addExperiment(page, {
      name: "stable convergence day 1",
      command: "cd code && bash run",
      output: "results/Day1_Exp1/stimulation_response_error.png",
    });
  });

  await demoStep(page, "Review the authored run scripts", async () => {
    await openPort(page, "Activation");
    await expect(main.getByText("Activation Run Script", { exact: true })).toBeVisible();
    await showDemoFocus(
      main.getByText("Activation Run Script", { exact: true }),
      "Each runnable owns its execution: the REE spec stores per-runnable run scripts, each a self-contained docker run",
    );
    await page.waitForTimeout(1400);
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
