import path from "node:path";
import { expect, type Locator, type Page, test } from "@playwright/test";
import { stepShot } from "../../screenshot";

const DEMO_STEP_DELAY_MS = 250;
const DEMO_NARRATION_DELAY_MS = 650;

const CAPSULE_NAME =
  "Fast and Accurate Core-Loss Measurement Using Twin Transformers With Dynamic Phase-Error Compensation";
const CAPSULE_DESCRIPTION =
  "Code Ocean capsule for transformer core-loss characterization across steady-state and transient waveform datasets from 100 kHz to 5 MHz.";
const BUILD_SCRIPT_PATH = "build_runtime.sh";
const PROVISION_SCRIPT_PATH = "codeocean_paths.sh";

const BUILD_RUNTIME_SCRIPT = `#!/usr/bin/env bash
set -euo pipefail

IMAGE="registry.codeocean.com/published/2a4f30ae-3bf0-47de-baff-97a73b515224:v1"
OUT="runtime.tar.gz"

docker pull --platform linux/amd64 "$IMAGE"
docker save "$IMAGE" -o "$OUT"
ls -lh "$OUT"
`;

const CODEOCEAN_PATHS_SCRIPT = `#!/usr/bin/env sh
set -eu

mkdir -p /workspace/results

if [ -e /data ] && [ ! -L /data ]; then
  mv /data /data.repo2ree-original
fi
if [ -e /results ] && [ ! -L /results ]; then
  mv /results /results.repo2ree-original
fi

ln -sfn /workspace/data /data
ln -sfn /workspace/results /results

chmod +x /workspace/code/run || true
`;

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

async function saveOverlayScript(page: Page, filePath: string, content: string) {
  const main = page.getByRole("main");
  await fillDemo(page, main.getByPlaceholder("build_runtime.sh").first(), filePath);
  await fillDemo(page, main.locator("textarea").first(), content);
  await clickDemo(page, main.getByRole("button", { name: /Save to overlay/ }));
  await expect(page.getByText(`Saved ${filePath} to workspace`)).toBeVisible({ timeout: 20000 });
}

async function pickWorkspaceFile(
  page: Page,
  placeholder: string,
  filePath: string,
  narration = `Pick ${filePath}`,
) {
  const input = page.getByPlaceholder(placeholder);
  await clickDemo(page, input.locator("..").getByTitle("Browse repository files"), narration);
  const option = page.getByRole("button", { name: filePath });
  await expect(option).toBeVisible({ timeout: 20000 });
  await clickDemo(page, option);
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
  await fillDemo(
    page,
    main.getByPlaceholder("pytest tests/smoke -q"),
    experiment.command,
    "Commands start at /workspace, so this command uses an explicit relative path",
  );
  await addFileShaOutput(page, experiment.output);
  await clickDemo(page, main.getByRole("button", { name: /Save & back to catalog/ }));
  await expect(main.getByRole("button", { name: experiment.name })).toBeVisible();
}

test("author Code Ocean capsule 4825344 inputs", async ({ page }) => {
  test.setTimeout(900000);

  const sourceArchive = path.resolve(
    __dirname,
    "../../../../examples/code-ocean/capsule-4825344.zip",
  );
  const main = page.getByRole("main");

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
    await expect(page.getByRole("region", { name: "Source Acquisition" })).toBeVisible();
  });

  await demoStep(page, "Upload Code Ocean capsule", async () => {
    await clickDemo(page, page.getByRole("button", { name: "Upload tarball" }));
    await page
      .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
      .setInputFiles(sourceArchive);
    await clickDemo(
      page,
      page.getByRole("button", { name: /Add to workspace/i }),
      "Extract capsule-4825344.zip into the REE workspace",
    );
    await expect(page.getByText("capsule-4825344.zip", { exact: true }).first()).toBeVisible({
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
    await page.getByPlaceholder("Filter files…").fill("exp_dataset");
    await expect(page.getByRole("button", { name: /exp_dataset\.zip/i }).first()).toBeVisible();
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
      "core-loss measurement",
      "damped oscillation",
      "transient measurement",
      "dynamic phase-error compensation",
    ]) {
      await addKeyword(page, keyword);
    }
    await addContributor(page, {
      id: "md-tanvir-ahammed",
      name: "Md Tanvir Ahammed",
      affiliation: "North Carolina State University",
    });
    await addContributor(page, {
      id: "wensong-yu",
      name: "Wensong Yu",
      affiliation: "North Carolina State University",
    });
  });

  await demoStep(page, "Create runtime scripts", async () => {
    await openPort(page, "Build");
    await expect(main.getByText("Build Runtime", { exact: true })).toBeVisible();
    await saveOverlayScript(page, BUILD_SCRIPT_PATH, BUILD_RUNTIME_SCRIPT);
    await saveOverlayScript(page, PROVISION_SCRIPT_PATH, CODEOCEAN_PATHS_SCRIPT);
    await pickWorkspaceFile(
      page,
      "Pick a .sh file from the workspace",
      BUILD_SCRIPT_PATH,
      `Select ${BUILD_SCRIPT_PATH} as the active build script`,
    );
    await expect(main.getByPlaceholder("Pick a .sh file from the workspace")).toHaveValue(
      BUILD_SCRIPT_PATH,
    );
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

  await demoStep(page, "Configure runtime entry", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("button", { name: "Open runtime environment" }),
      "Open the shared runtime-entry configuration",
    );
    await expect(main.getByText("Runtime Environment", { exact: true })).toBeVisible();
    await fillDemo(
      page,
      main.getByPlaceholder(/--volume \/data:\/data/),
      "--platform linux/amd64",
      "Use Code Ocean's linux/amd64 platform flag without host bind mounts",
    );
    await fillDemo(
      page,
      main.getByPlaceholder("runs in the substrate after it is up"),
      PROVISION_SCRIPT_PATH,
      "Provision aliases for Code Ocean's absolute /data and /results paths",
    );
    await expect(main.getByText("Setup", { exact: true }).first()).toBeVisible({
      timeout: 20000,
    });
  });

  await demoStep(page, "Author activation command", async () => {
    await openPort(page, "Activation");
    await expect(main.getByText("Activation Command", { exact: true })).toBeVisible();
    await fillDemo(
      page,
      main.getByPlaceholder(/e\.g\. python/).first(),
      "cd code && python -c \"import numpy, scipy, pandas, matplotlib, tabulate; from pathlib import Path; assert Path('/data/exp_dataset.zip').is_file(); assert Path('/results').is_dir(); print('activation ok')\"",
      "Activation starts from /workspace and explicitly enters code/",
    );
    await expect(main.getByText("What actually runs", { exact: true })).toBeVisible();
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
      name: "steady-state 5000 kHz",
      command: "cd code && bash run",
      output: "/results/Steady_state_Bm_vs_Pcore_5000kHz.png",
    });
    await addExperiment(page, {
      name: "transient 5000 kHz",
      command: "cd code && python -u Tran_waveform.py",
      output: "/results/Transient_Bm_vs_Pcore_5000kHz.png",
    });
  });

  await demoStep(page, "Review authored command plan", async () => {
    await openPort(page, "Activation");
    await expect(main.getByText("What actually runs", { exact: true })).toBeVisible();
    await showDemoFocus(
      main.getByText("What actually runs", { exact: true }),
      "The REE spec stores the runtime entry and runnable commands; this plan is derived from the same executor builders",
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
