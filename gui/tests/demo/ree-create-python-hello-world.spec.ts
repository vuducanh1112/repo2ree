import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  dockerRunScript,
  EXPERIMENT_OUTPUT_FILE,
  stdoutContainsVerifyScript,
} from "../e2e/helpers/flow";
import { createDemoKit } from "./helpers/demo";

const PYTHON_RUNTIME_PATH = "python_hello_world/runtime.tar";

const {
  demoStep,
  clickDemo,
  fillDemo,
  saveRunScript,
  saveVerifyScript,
  generateScriptDemo,
  showcaseScroll,
  showcasePanel,
} = createDemoKit({ stepDelayMs: 350, narrationDelayMs: 900 });

test("author, seal, and download a Python hello-world REE", async ({ page }) => {
  // DinD: every workbench builds against a cold (empty) image cache, so the
  // build/activation/experiment steps are full cold pulls + installs. Combined
  // with the narration delays — and the three script-generation chapters, each a
  // real inference round-trip plus dwell time — this needs a much larger budget
  // than warm runs.
  test.setTimeout(540000);

  const sourceArchive = path.resolve(
    __dirname,
    "../../../examples/projects/python-hello-world.tar.gz",
  );
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
  // Source acquisition is a floating hub panel (role=region), not a docked
  // page; its Clear-source action lives in that panel's header.
  const sourcePanel = page.getByRole("region", { name: "Source Acquisition" });
  const clearSourceButton = sourcePanel.getByRole("button", { name: /Clear source/i });

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
    // Provisioning lands on the canvas hub; decompose before source acquisition
    // so the whole authoring walkthrough happens against the shell view.
    // Generous budget: the lean bench path pulls the image, starts the bench,
    // and runs the doctor probe (which waits for the in-bench dockerd) —
    // ~20s warm, longer on a cold registry pull.
    await expect(
      page.getByRole("navigation").getByRole("button", { name: "Source", exact: true }),
    ).toBeVisible({ timeout: 120000 });
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
    // Acquisition names the source type from the uploaded archive itself — a
    // .tar.gz is a tarball — and the snapshot reads it back off the definition.
    const snapshot = page.getByRole("region", { name: "Workspace Snapshot" });
    await expect(snapshot.getByText("tarball", { exact: true })).toBeVisible();
  });

  await demoStep(page, "Browse extracted files", async () => {
    // Files live in the file-tree HUD console docked on the canvas; leave the
    // source dock and expand it.
    await page.keyboard.press("Escape");
    await clickDemo(
      page,
      page.getByRole("button", { name: "Expand files" }),
      "Browse the REE's own files in the docked file console",
    );

    await expect(page.getByRole("button", { name: "Collapse files" })).toBeVisible();
    // This console browses the REE tree, which excludes `workspace/` — the
    // materialized view has its own inventory and its own surface. An uploaded
    // archive lands in `upstream/`, the acquired source.
    await page.getByPlaceholder("Filter files…").fill("upstream");
    for (const nodeName of archiveNodeNames) {
      const escapedNodeName = nodeName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      await expect(page.getByRole("button", { name: new RegExp(escapedNodeName) })).toBeVisible();
    }
    await clickDemo(
      page,
      page.getByRole("button", { name: /main\.py/i }).first(),
      "Inspect the uploaded files. Here: upstream/python_hello_world/main.py",
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
      "Assess the source declarations and surface reproducibility risks",
    );
    await expect(main.getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible({
      timeout: 60000,
    });
    // The earned-outcome badge (role=status) renders only for a succeeded run.
    await expect(main.getByRole("status", { name: "Evaluated" })).toBeVisible();
    await showcasePanel(page, main.getByText("Run Log").first(), "Review output logs");
  });

  await demoStep(page, "Generate a build script from the repository", async () => {
    // Decomposed, the inner shell itself is the build runtime — click it to open
    // the Build Runtime page (there is no separate Build panel in this view).
    await page.keyboard.press("Escape").catch(() => {});
    await expect(page.getByRole("button", { name: "Reassemble" })).toBeVisible();
    await clickDemo(
      page,
      page.getByRole("button", { name: "Open build runtime" }),
      "Open the inner shell: the build runtime the whole REE executes on",
    );
    await expect(main.getByText("Build Runtime", { exact: true })).toBeVisible();

    // Before authoring by hand: ask repo2ree what it can infer from the sources
    // alone. This reads the immutable upstream tree only — it never runs, never
    // writes, and never inspects its own output.
    await generateScriptDemo(page, {
      action:
        "Ask repo2ree to infer a build script from the repository — read-only: it scans the acquired sources, nothing is saved",
      result:
        "It found the project’s Dockerfile and proposed a complete build. Both a Dockerfile and a requirements.txt are viable here, so this is a decision the author confirms — not a silent default",
      graph:
        "Open the decision graph — inference explains itself with the versioned DAG it actually walked, so a proposal is never a black box",
    });
  });

  await demoStep(page, "Build runtime", async () => {
    await fillDemo(
      page,
      main.getByLabel("Build script"),
      `#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
PROJECT_DIR="python_hello_world"
RUNTIME_FILE="$PROJECT_DIR/runtime.tar"

echo "Building $IMAGE_NAME:$TAG from $PROJECT_DIR..."
docker build -t "$IMAGE_NAME:$TAG" "$PROJECT_DIR"

echo "Exporting image to $RUNTIME_FILE..."
docker save "$IMAGE_NAME:$TAG" -o "$RUNTIME_FILE"
`,
      "The proposal is a starting point, not a verdict: the author edits REE’s canonical build script directly — build the image from the project Dockerfile and save it to the workspace",
    );
    await clickDemo(page, main.getByRole("button", { name: "Save build script" }));

    // The runtime the build produces is declared before it runs — the build
    // refuses to start without it and fails if nothing lands at that path. The
    // declaration names the substrate the whole REE runs on, shared by
    // activation and every experiment.
    await fillDemo(
      page,
      page.getByRole("region", { name: "Runtime artifact" }).getByRole("textbox"),
      PYTHON_RUNTIME_PATH,
      "Declare where the build writes the runtime — the build is checked against this path",
    );

    // The build page has no shared execution lifecycle — each
    // experiment and the activation own their own run script (authored later).
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
    // Re-build appears for failed runs too; the "Built" outcome badge is
    // success-only, so a failed build stops the demo here with its log visible.
    await showcasePanel(
      page,
      main.getByRole("status", { name: "Built" }),
      "The build succeeded and earned its badge",
    );
  });

  await demoStep(page, "Generate SBOM", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "SBOM", exact: true }),
      "Open the SBOM page — a full step page like Build Runtime",
    );
    await clickDemo(page, main.getByRole("button", { name: /^Generate$/ }), "Run SBOM scan");
    await expect(main.getByRole("button", { name: /^Regenerate$/ })).toBeVisible({
      timeout: 60000,
    });
    // The status chip and the earned-outcome badge share the "SBOM ready" text;
    // the role=status badge is the success-only signal.
    await expect(main.getByRole("status", { name: "SBOM ready" })).toBeVisible({
      timeout: 60000,
    });
    await showcasePanel(page, main.getByText(/SBOM log/i).first(), "Review SBOM logs");
  });

  await demoStep(page, "Cross-check SBOM against declared dependencies", async () => {
    // The cross-check joins the runtime SBOM with the dependency inventory the
    // Evaluate step scanned: which declared deps actually made it into the
    // built runtime, and what runs in it that no manifest declared.
    const crossCheckButton = main.getByRole("button", { name: /^Cross-check$/ });
    await expect(crossCheckButton).toBeEnabled({ timeout: 30000 });
    await clickDemo(
      page,
      crossCheckButton,
      "Cross-check the SBOM against the scanned dependency inventory",
    );
    await expect(main.getByRole("button", { name: /^Re-check$/ })).toBeVisible({
      timeout: 60000,
    });
    // pandas==2.2.1 is the only declared dep and it is in the runtime; its
    // transitive installs (numpy, pytz, ...) surface as undeclared packages.
    await showcasePanel(
      page,
      main.getByText(/declared deps in runtime/),
      "The verdicts: declared deps observed in the runtime, plus what the runtime carries undeclared",
    );
  });

  await demoStep(page, "Generate an activation script from the built runtime", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await clickDemo(
      page,
      page.getByRole("navigation").getByRole("button", { name: "Activation", exact: true }),
      "Open activation test",
    );
    await expect(main.getByText("Activation Run Script", { exact: true })).toBeVisible();

    // The runtime artifact exists and is declared now, so inference inspects the
    // built image itself rather than guessing from the sources.
    await generateScriptDemo(page, {
      action:
        "Infer the activation script — this time from the built runtime: repo2ree reads the saved image and derives the docker plumbing",
      result:
        "The load-and-run wrapper was inferred, but the activation command was not. repo2ree never guesses what proves a runtime is usable — the scaffold is fail-closed and exits 64 until the author fills it in",
      graph:
        "The graph shows how the runtime contract was resolved: the declared artifact was inspected, and its single image reference settled the docker branch",
    });
  });

  await demoStep(page, "Test activation", async () => {
    await saveRunScript(
      page,
      main.getByRole("textbox", { name: "Activation run script", exact: true }),
      dockerRunScript("python -c \"import sys; print('ok')\"", PYTHON_RUNTIME_PATH),
      "The author supplies the missing piece: a finite command that proves the image starts, in a self-contained docker run",
    );
    await clickDemo(
      page,
      main.getByRole("button", { name: /Run activation/ }),
      "Execute activation",
    );
    await expect(main.getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 90000 });
    // Success-only outcome badge — a failed activation stops the demo here.
    await showcasePanel(
      page,
      main.getByRole("status", { name: "Activation passed" }),
      "The runtime starts — activation earned its badge",
    );
    await showcasePanel(page, main.getByText(/Activation log/i).first(), "Review activation logs");
  });

  await demoStep(page, "Declare an experiment", async () => {
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
    await fillDemo(
      page,
      main.getByPlaceholder("smoke-test"),
      "python-hello",
      "Name the experiment — naming it declares it on the REE and settles its reserved script paths",
    );
  });

  await demoStep(page, "Generate the experiment run script", async () => {
    // Inference is gated on the experiment being declared: it will only generate
    // for an experiment the REE actually carries.
    await generateScriptDemo(page, {
      action:
        "Infer this experiment’s run script — it generates only for a declared experiment, and only once a runtime is resolved",
      result:
        "Same shape as activation: the runtime plumbing and the result-capture wiring were inferred, while the scientific command — the one claim that must be the author’s — was deliberately left blank",
      graph:
        "Activation and experiments share one versioned runtime-contract subgraph; only the leaf that renders the script differs",
    });
  });

  await demoStep(page, "Run experiment", async () => {
    await saveRunScript(
      page,
      main.getByRole("textbox", { name: "Experiment run script", exact: true }),
      dockerRunScript(
        "python python_hello_world/main.py",
        PYTHON_RUNTIME_PATH,
        EXPERIMENT_OUTPUT_FILE,
      ),
      "The experiment owns its full run: load the image and docker run the script in the mounted workspace, teeing stdout to a workspace file",
    );
    await saveVerifyScript(
      page,
      main.getByRole("textbox", { name: "Experiment verify script", exact: true }),
      stdoutContainsVerifyScript("Pandas Hello World"),
      "Write the verify script: a plain script that reads the run's output file back — its exit code is the verdict",
    );
    await fillDemo(
      page,
      main.getByRole("textbox", { name: "Output files" }),
      EXPERIMENT_OUTPUT_FILE,
      "Declare the result file the run produces — captured after every run and, once opted in on the Seal page, shipped as the author baseline",
    );
    await clickDemo(page, main.getByRole("button", { name: /^Run$/ }), "Run the experiment");
    await page.waitForTimeout(5000);
    await showcaseScroll(page, 800);
    await showcaseScroll(page, 800);
    await page.waitForTimeout(5000);
    const runResultPanel = main.getByRole("region", { name: "Run result" });
    await expect(runResultPanel.getByText("pass", { exact: true })).toBeVisible({ timeout: 90000 });
    await expect(runResultPanel.getByText(/declared validation passed/)).toBeVisible();
  });

  await demoStep(page, "Review decomposed experiment view", async () => {
    await page.keyboard.press("Escape").catch(() => {});
    await expect(page.getByRole("button", { name: "Reassemble" })).toBeVisible();
    await showcasePanel(
      page,
      // Exact: once the run records a receipt, the receipts console carries a
      // card named after the same experiment ("Experiment run · python-hello").
      page.getByRole("button", { name: "python-hello", exact: true }),
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
    // The seal panel shows source/runtime bundle toggles inline before sealing.
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

    // Persist the sealed bundle so the demo leaves a real, runnable artifact
    // (run.sh + ree/...) under the test output dir, and attach it to the report.
    const bundlePath = test.info().outputPath(download.suggestedFilename());
    await download.saveAs(bundlePath);
    await test.info().attach("sealed-ree-bundle", {
      path: bundlePath,
      contentType: "application/zip",
    });
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

  await demoStep(page, "Find the sealed REE in the index", async () => {
    // The point of this chapter is what just happened in the previous one: the
    // workbench — container, volume, and every file in it — is gone, and the
    // REE is still here. Sealing recorded it host-side, so the record outlives
    // the bench it was authored in.
    await clickDemo(
      page,
      page.getByRole("button", { name: /REE Index/i }),
      "Open the REE index — the record of everything sealed on this control plane",
    );
    await expect(page.getByRole("heading", { name: "REE Index" })).toBeVisible();

    const entry = page.getByText("ree-hello-world", { exact: true });
    await showcasePanel(
      page,
      entry,
      "The REE just sealed is listed — its workbench is released, but the record survives it",
    );

    // Identity is the seal digest, not the name: the name is a label two nodes
    // could disagree on, while the digest is what a deposit would be bound to.
    await expect(page.getByText(/^[0-9a-f]{12}$/)).toBeVisible();

    await showcasePanel(
      page,
      page.getByText("Not deposited", { exact: true }),
      "No DOI yet — nothing has been deposited to an archive, and the index says so rather than leaving it blank",
    );

    // The filter is the honest counterpart: only entries an archive has issued
    // an identifier for are citable elsewhere, and this REE is not one yet.
    await clickDemo(
      page,
      page.getByRole("button", { name: /Deposited only/i }),
      "Filter to what an archive has actually accepted — this REE is sealed, not yet deposited, so it drops out",
    );
    await expect(page.getByText("Nothing deposited yet")).toBeVisible();
    await expect(page.getByText("ree-hello-world", { exact: true })).toHaveCount(0);
  });
});
