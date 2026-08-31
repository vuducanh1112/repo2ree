import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, type Locator, type Page } from "@playwright/test";
import { FIXTURES_DIR } from "../../artifacts";
import { stepShot } from "../../screenshot";

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

// Example inputs are shared across suites (and the API walkthrough), so they
// live at the repository root rather than under this suite.
const EXAMPLES_DIR = path.resolve(__dirname, "../../../../examples");

/** Absolute path to the bundled Python hello-world source archive. */
export function pythonHelloWorld(): string {
  return path.join(EXAMPLES_DIR, "projects/python-hello-world.tar.gz");
}

/**
 * Absolute path to a complete, already-authored REE, packaged the way
 * `ree-archive` downloads one.
 *
 * The reviewer suite's baseline: it carries real author evidence — the frozen
 * snapshot, the overlay scripts, the SBOM, and the author receipts for build,
 * SBOM, activation and the experiment — so a review has something to reproduce
 * *against* without the suite authoring it first. See `examples/README.md` for
 * what it deliberately omits (the seal stamps, and the 327 MB runtime tarball).
 */
export function authoredRee(): string {
  return path.join(EXAMPLES_DIR, "rees/ree-hello-world.zip");
}

/**
 * Absolute path to the pip-based Python hello-world source archive (no
 * Dockerfile — the workbench itself is the Python runtime). Packed on demand
 * from the checked-in sources into the gitignored artifact root, so no binary
 * blob lives in the repo — and repacked on every call, which is what keeps
 * test-artifacts/ safe to delete even though a test reads this back.
 */
export function pythonPipHelloWorld(): string {
  mkdirSync(FIXTURES_DIR, { recursive: true });
  const archive = path.join(FIXTURES_DIR, "python-pip-hello-world.tar.gz");
  execFileSync("tar", [
    "-czf",
    archive,
    "-C",
    path.join(EXAMPLES_DIR, "projects"),
    "python_pip_hello_world",
  ]);
  return archive;
}

/**
 * A self-contained run script for a runnable (activation or experiment). In the
 * new model each runnable owns its full execution: load the built runtime image
 * if it isn't already present, then enter it with its own `docker run`,
 * bind-mounting the workspace so declared file outputs surface on the host.
 *
 * When `outputFile` is given the run's stdout is materialized to that
 * workspace-relative file (via `tee`) so a verify script can read it back —
 * there are no magic variables handing stdout to verification.
 */
export function dockerRunScript(command: string, runtimePath: string, outputFile?: string): string {
  const capture = outputFile ? ` | tee ${JSON.stringify(outputFile)}` : "";
  return `#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
RUNTIME_FILE=${JSON.stringify(runtimePath)}

if ! docker image inspect "$IMAGE_NAME:$TAG" >/dev/null 2>&1; then
  docker load < "$RUNTIME_FILE"
fi

docker run --rm \\
  -v "$(pwd):/workspace" \\
  -w /workspace \\
  "$IMAGE_NAME:$TAG" \\
  ${command}${capture}
`;
}

/**
 * Workspace file the experiment run script materializes its stdout to. Declared
 * as the experiment's output (see `runExperiment`) so a successful run captures
 * it into the produced-results store, and sealed into the bundle as the author
 * baseline a reviewer diffs against.
 */
export const EXPERIMENT_OUTPUT_FILE = "result.txt";

export function main(page: Page) {
  return page.getByRole("main");
}

/**
 * The three outcomes the "Generate from repository" control reports. Matching
 * any of them is how a spec knows the inference round-trip settled — the status
 * line renders only once the mutation resolves.
 */
export const GENERATE_STATUS = /Loaded a generated|could be inferred yet|Generation failed/;

/**
 * Run read-only script inference from the generate control in its workspace drawer,
 * then expand the decision graph it renders.
 *
 * Inference never writes: it loads a candidate into the editor (leaving it
 * dirty) and explains itself with the executed decision DAG. The graph is
 * rendered whether or not a candidate was produced, so callers can assert on it
 * either way. Returns the status message and the graph text.
 */
export async function generateScript(
  page: Page,
): Promise<{ message: string; graph: string; script: string }> {
  await stepShot(page, "generate-script", "before");
  const content = main(page);
  // The generated body is read from the response rather than the editor. The
  // editor is a fixed-height CodeMirror viewport that virtualizes past what it
  // can show, so the tail of a scaffold — the `exit 64` that makes it
  // fail-closed — is legitimately absent from the DOM, and what these callers
  // are asserting about is the generator's output anyway.
  const [response] = await Promise.all([
    page.waitForResponse(
      (candidate) =>
        candidate.url().includes("script-inferences:generate") &&
        candidate.request().method() === "POST",
      { timeout: 30000 },
    ),
    content
      .getByRole("button", { name: /Generate from repository/ })
      .first()
      .click(),
  ]);
  const report = (await response.json()) as {
    results?: { candidates?: { body?: string | null }[] }[];
  };
  const script = report.results?.[0]?.candidates?.[0]?.body ?? "";

  const status = content.getByText(GENERATE_STATUS).first();
  // A real backend round-trip: rescan + DAG walk (and, before the artifact
  // exists, a build-script regeneration), so allow well past the default.
  await expect(status).toBeVisible({ timeout: 30000 });
  const message = (await status.textContent()) ?? "";

  // The decision graph is collapsed by default — open it and read it back.
  const summary = content.getByText("Decision graph", { exact: true }).first();
  await expect(summary).toBeVisible();
  await summary.click();
  const graphBlock = content
    .locator("details")
    .filter({ hasText: "Decision graph" })
    .locator("pre")
    .first();
  await expect(graphBlock).toBeVisible();
  const graph = (await graphBlock.textContent()) ?? "";

  await stepShot(page, "generate-script", "after");
  return { message, graph, script };
}

/**
 * Await the definition PATCH a declaration settles through — and fail here if
 * the backend rejected it. A rejected patch leaves the declaration unmade, so a
 * helper that merely waited for *a* response would hand the spec a REE missing
 * what it just declared, and the failure would surface pages later as something
 * else entirely (inference reporting an experiment it cannot resolve).
 */
async function waitForDefinitionPatch(page: Page, { expectOk = true } = {}) {
  const response = await page.waitForResponse(
    (res) => res.url().includes("/definition") && res.request().method() === "PATCH",
  );
  if (expectOk && !response.ok()) {
    throw new Error(
      `definition PATCH rejected with ${response.status()}: ${await response.text()}`,
    );
  }
  return response;
}

/**
 * Await the workspace-file write a script save always performs.
 *
 * Prefer this over {@link waitForDefinitionPatch} for a save whose definition PATCH
 * is *conditional* — the experiment page only re-declares a script path when it
 * differs from the one already on the definition, so once the backend has settled
 * that path (naming an experiment does exactly that) a save writes the file and
 * patches nothing. The PUT is the signal that always fires.
 */
function waitForFileWrite(page: Page) {
  return page.waitForResponse(
    (res) => res.url().includes("/files/content") && res.request().method() === "PUT",
  );
}

/**
 * The canvas hub. Navigation lives here as pod "nodes" (Source, Metadata,
 * Reproducibility Readiness, Build, Hardware, Experiments, Archive, Seal) floating around
 * the specimen pod — scope clicks here so short node labels don't collide with
 * same-named main buttons.
 */
function nav(page: Page) {
  return page.getByRole("navigation", { name: "Workspace pages" });
}

/**
 * Open a canvas node by its exact label. The selected page replaces the current
 * drawer contents while the canvas remains mounted beside it.
 */
export async function openPort(page: Page, label: string) {
  await nav(page).getByRole("button", { name: label, exact: true }).click();
}

/** Open the file console from the persistent workspace status bar. */
export async function openFilesConsole(page: Page) {
  const status = page.getByRole("region", { name: "Workspace status" });
  const trigger = status.getByRole("button", { name: /^Files/ });
  if ((await trigger.getAttribute("aria-pressed")) !== "true") await trigger.click();
  await expect(page.getByRole("button", { name: "Collapse files" })).toBeVisible();
}

/**
 * How many connected agents the lab-location picker offers. Specs that need
 * more than one agent (multi-agent, stress) call this first and skip when the
 * stack is smaller — the count is a property of whatever stack the suite runs
 * against (source, image, or published), not something the tests control.
 */
export async function connectedAgentCount(page: Page): Promise<number> {
  await page.goto("/");
  await page.getByRole("button", { name: "Create a new REE" }).click();
  await expect(page.getByRole("heading", { name: "Where should this REE run?" })).toBeVisible();
  const cards = page.getByRole("button", { name: /connected/ });
  // The agent list loads async; a suite-worthy stack always has at least one
  // agent, so waiting for the first card is enough for a settled count.
  await cards.first().waitFor({ state: "visible" });
  return cards.count();
}

/**
 * Land on the workbench lab from the landing view. REE creation opens with
 * the lab-location step: pick the (connected) agent that will host the
 * workbench, which carries its id into the workbench/image page.
 *
 * `agentIndex` picks the nth connected agent (default: the first) — the
 * multi-agent spec uses it to pin each session to a different agent. Returns
 * the chosen agent's id, read back from the workspace URL the picker
 * navigates to.
 */
export async function startReeCreation(page: Page, options?: { agentIndex?: number }) {
  await page.goto("/");
  await stepShot(page, "start-ree-creation", "before");
  await page.getByRole("button", { name: "Create a new REE" }).click();
  await expect(page.getByRole("heading", { name: "Where should this REE run?" })).toBeVisible();
  await page
    .getByRole("button", { name: /connected/ })
    .nth(options?.agentIndex ?? 0)
    .click();
  // Choosing a bay opens workbench setup over the picker: one screen, not two.
  await expect(page.getByRole("region", { name: "Set up the workbench" })).toBeVisible();
  await stepShot(page, "start-ree-creation", "after");
  // The URL no longer carries the agent — nothing navigates until the bench is
  // provisioned — so the armed bay is what records which lab was chosen.
  return (await page.locator("[data-lab][aria-pressed='true']").getAttribute("data-lab")) ?? "";
}

/**
 * Provision the workbench container. Provisioning lands on the hub canvas
 * (the live lab), so this resolves there and then dives into the Source node so
 * the rest of the walkthrough continues from the docked authoring drawer.
 */
export async function provisionWorkbench(page: Page, options?: { imageRef?: string }) {
  await stepShot(page, "provision-workbench", "before");
  // Setup is the drawer the lab picker opens, so scope to it rather than to a
  // page that no longer exists on its own.
  const setup = page.getByRole("region", { name: "Set up the workbench" });
  if (options?.imageRef) {
    // Pick "Custom…" in the image selector and provide the reference — the
    // catalog default (docker:dind) stays untouched for every other test.
    await setup.getByRole("button", { name: /Custom…/ }).click();
    await setup.getByPlaceholder("e.g. docker.io/library/docker:29-dind").fill(options.imageRef);
  }
  await setup.getByRole("button", { name: /Provision workbench/i }).click();
  // A real provision: bench container start, nested dockerd boot, doctor
  // probe. ~15-20s depending on the agent's environment — well past the
  // project's default expect timeout.
  await expect(nav(page).getByRole("button", { name: "Source", exact: true })).toBeVisible({
    timeout: 90000,
  });
  await openPort(page, "Source");
  await expect(
    page.getByRole("region", { name: "Source Acquisition" }).getByText("Source Acquisition", {
      exact: true,
    }),
  ).toBeVisible();
  await stepShot(page, "provision-workbench", "after");
}

/**
 * Provision a workbench with an already-authored REE loaded onto it.
 *
 * The bundle is chosen during provisioning rather than after it, because the
 * load runs on the workbench this step creates — so this replaces
 * {@link provisionWorkbench} rather than following it. What comes back is a lab
 * holding another author's evidence and nothing of this suite's own, which is
 * exactly the position a reviewer is in.
 */
export async function provisionFromBundle(page: Page, bundlePath: string) {
  await stepShot(page, "provision-from-bundle", "before");
  await page.getByLabel("REE bundle").setInputFiles(bundlePath);
  await expect(page.getByText(/This workbench will be loaded with the uploaded REE/)).toBeVisible();
  // The control renames itself once a bundle is chosen — provisioning and
  // loading are one action here, so waiting for "Provision workbench" would
  // wait for a button this screen no longer has.
  await page.getByRole("button", { name: /Provision and load REE/i }).click();
  // Provisioning plus the load itself: bench container start, nested dockerd
  // boot, doctor probe, then unpacking the bundle's evidence into the REE.
  await expect(nav(page).getByRole("button", { name: "Source", exact: true })).toBeVisible({
    timeout: 120000,
  });
  await stepShot(page, "provision-from-bundle", "after");
}

/** Upload a tarball into the workspace and wait for the snapshot to settle. */
export async function uploadSource(page: Page, archivePath: string) {
  await stepShot(page, "upload-source", "before");
  await page.getByRole("button", { name: "Upload tarball" }).click();
  await page
    .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
    .setInputFiles(archivePath);
  await page.getByRole("button", { name: /Add to workspace/i }).click();

  // The clear-source action lives in the source hub panel header (top-right).
  const clearSource = page
    .getByRole("region", { name: "Source Acquisition" })
    .getByRole("button", { name: /Clear source/i });
  await expect(clearSource).toBeVisible();
  await stepShot(page, "upload-source", "after");
  return clearSource;
}

/**
 * Fetch a source from an origin URL (the "Use origin URL" path) and wait for the
 * snapshot to settle. Selects the source type first so the git-only revision
 * field renders before it is filled; leave `revision` blank to fetch HEAD.
 */
export async function downloadSource(
  page: Page,
  origin: { url: string; sourceType?: "git" | "tarball" | "zip"; revision?: string },
) {
  await stepShot(page, "download-source", "before");
  const region = page.getByRole("region", { name: "Source Acquisition" });
  await region.getByRole("button", { name: "Use origin URL", exact: true }).click();
  await page.getByPlaceholder("https://github.com/org/repo").fill(origin.url);
  await region.getByRole("combobox").selectOption(origin.sourceType ?? "git");
  if (origin.revision) {
    await page.getByPlaceholder(/Revision \(commit, branch, or tag\)/).fill(origin.revision);
  }
  await region.getByRole("button", { name: /Download source to workspace/i }).click();

  // A real git fetch against a remote (cold, no cache) — allow a generous budget.
  const clearSource = region.getByRole("button", { name: /Clear source/i });
  await expect(clearSource).toBeVisible({ timeout: 90000 });
  await stepShot(page, "download-source", "after");
  return clearSource;
}

/** Fill in project identity metadata. */
export async function provideMetadata(
  page: Page,
  meta: { name: string; version: string; description: string },
) {
  await stepShot(page, "provide-metadata", "before");
  await openPort(page, "Metadata");
  await expect(main(page).getByRole("heading", { name: "Metadata", exact: true })).toBeVisible();
  await page.getByPlaceholder("deepfold-protein-structure-prediction").fill(meta.name);
  await page.getByPlaceholder("1.0.0").fill(meta.version);
  await page.getByPlaceholder("REE for reproducible execution of...").fill(meta.description);
  await stepShot(page, "provide-metadata", "after");
}

/** Run the source-repository assessment and wait for its findings. */
export async function runEvaluate(page: Page) {
  await stepShot(page, "run-evaluate", "before");
  await openPort(page, "Reproducibility Readiness");
  await expect(
    main(page).getByRole("heading", { name: "Reproducibility Readiness", exact: true }),
  ).toBeVisible();
  await main(page)
    .getByRole("button", { name: /^Run Evaluate$/ })
    .click();
  await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible({
    timeout: 20000,
  });
  await stepShot(page, "run-evaluate", "after");
}

/**
 * Build the runtime artifact. Declaring where the build writes it and running
 * the build both live on the single Build Runtime page — see
 * {@link declareRuntimeArtifact}, which must happen first: the build refuses to
 * run until the produced path is declared.
 */
export function dockerBuildScript(projectDir: string, producedRuntimePath: string): string {
  return `#!/usr/bin/env sh
set -eu

IMAGE_NAME="pandas-hello"
TAG="latest"
PROJECT_DIR=${JSON.stringify(projectDir)}
RUNTIME_FILE=${JSON.stringify(producedRuntimePath)}

docker build -t "$IMAGE_NAME:$TAG" "$PROJECT_DIR"
docker save "$IMAGE_NAME:$TAG" -o "$RUNTIME_FILE"
`;
}

export async function buildRuntime(page: Page, buildScript: string, producedRuntimePath: string) {
  await stepShot(page, "build-runtime", "before");
  await openPort(page, "Build");
  await expect(
    main(page).getByRole("heading", { name: "Build Runtime", exact: true }),
  ).toBeVisible();
  // REE owns one reserved build script — author the whole build in it directly
  // (produce the runtime artifact and land it in the workspace).
  await page.getByLabel("Build script").fill(buildScript);
  await main(page).getByRole("button", { name: "Save build script" }).click();

  await declareRuntimeArtifact(page, producedRuntimePath);

  await main(page)
    .getByRole("button", { name: /Run build/ })
    .click();
  // DinD: each workbench daemon starts with an empty image cache, so the first
  // build is a cold pull + install (~30s+), not a warm shared-cache build.
  await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible({
    timeout: 90000,
  });

  // Re-build appears for failed runs too. The earned-outcome badge
  // (role="status") renders only for a succeeded run, so a failed build fails
  // this step with its log on screen instead of surfacing 20s later as an
  // artifact-picker timeout.
  await expect(main(page).getByRole("status", { name: "Built" })).toBeVisible();
  await stepShot(page, "build-runtime", "after");
}

/**
 * Author a runnable's run script: fill the RunScriptCard editor, then click
 * its "Save run script" button (shared by the activation and experiment
 * editors).
 */
async function saveRunScript(page: Page, editor: Locator, content: string) {
  await editor.fill(content);
  await main(page).getByRole("button", { name: "Save run script", exact: true }).first().click();
}

/** Author and declare a runnable's verify script. */
async function saveVerifyScript(page: Page, editor: Locator, content: string) {
  await editor.fill(content);
  await main(page).getByRole("button", { name: "Save verify script", exact: true }).first().click();
}

export function stdoutContainsVerifyScript(expectedStdout: string): string {
  return `#!/usr/bin/env sh
set -eu

# The run script materialized its stdout to this workspace file; read it back.
EXPECTED=${JSON.stringify(expectedStdout)}
grep -Fq "$EXPECTED" ${JSON.stringify(EXPERIMENT_OUTPUT_FILE)}
`;
}

/**
 * Declare where the build will write its runtime. The runtime artifact card
 * lives on the Build Runtime page itself (section "1. Declare the runtime the
 * build produces"), and the declaration is authored before the build runs — the
 * path names a file that does not exist yet.
 */
async function declareRuntimeArtifact(page: Page, producedRuntimePath: string) {
  // Declaring the runtime is a debounced intent PATCH. The build reads the
  // declaration server-side, and anything else that asks the backend about the
  // runtime next (script inference, most obviously) must not race it, so settle
  // the declaration here rather than in each caller.
  const runtimeDeclared = waitForDefinitionPatch(page);
  await page
    .getByRole("region", { name: "Runtime artifact" })
    .getByRole("textbox")
    .fill(producedRuntimePath);
  await runtimeDeclared;
}

/** Add a hardware BOM entry (a CPU component with a device model). */
export async function provideHbom(page: Page, cpuModel: string) {
  await stepShot(page, "provide-hbom", "before");
  await openPort(page, "Hardware");
  await expect(
    main(page).getByRole("heading", { name: "Hardware BOM", exact: true }),
  ).toBeVisible();
  await main(page).locator("button").filter({ hasText: "Add CPU" }).first().click();
  const deviceModel = main(page).getByPlaceholder("Intel Core i9-14900K").first();
  await deviceModel.fill(cpuModel);
  await expect(deviceModel).toHaveValue(cpuModel);
  await stepShot(page, "provide-hbom", "after");
}

/**
 * Where the REE keeps its SBOM. Not a workspace file: the scan writes straight
 * into the REE's own `artifacts/`, and the page reads it from there.
 */
export const SBOM_ARTIFACT_PATH = "artifacts/sbom.json";

/**
 * Generate the SBOM. Navigates to the SBOM canvas node (a drawer page, like
 * Build Runtime).
 */
export async function generateSbom(page: Page) {
  await stepShot(page, "generate-sbom", "before");
  await openPort(page, "SBOM");
  const content = main(page);
  await expect(content.getByRole("button", { name: /^Generate$/ })).toBeVisible();
  await content.getByRole("button", { name: /^Generate$/ }).click();
  await expect(content.getByRole("button", { name: /^Regenerate$/ })).toBeVisible({
    timeout: 20000,
  });
  await expect(content.getByText("SBOM ready", { exact: true }).first()).toBeVisible({
    timeout: 20000,
  });
  // "Ready" means the declared path resolved to a real file. Asserting the path
  // pins where that file is: the REE's artifacts, not the materialized tree.
  await expect(content.getByText(SBOM_ARTIFACT_PATH, { exact: true }).first()).toBeVisible();
  await stepShot(page, "generate-sbom", "after");
}

/**
 * Cross-check the generated SBOM against the scanned dependency inventory,
 * from the same docked SBOM page. Requires evaluate and generate-sbom to have
 * run first — the cross-check joins the report with the SBOM.
 */
export async function crossCheckSbom(page: Page) {
  await stepShot(page, "cross-check-sbom", "before");
  await openPort(page, "SBOM");
  const content = main(page);
  await expect(content.getByRole("button", { name: /^Cross-check$/ })).toBeEnabled({
    timeout: 20000,
  });
  await content.getByRole("button", { name: /^Cross-check$/ }).click();
  // The card flips to Re-check once the run lands and the report refreshes.
  await expect(content.getByRole("button", { name: /^Re-check$/ })).toBeVisible({
    timeout: 30000,
  });
  await expect(content.getByText("Cross-checked", { exact: true })).toBeVisible();
  await expect(content.getByText(/declared deps in runtime/)).toBeVisible();
  await stepShot(page, "cross-check-sbom", "after");
}

/**
 * Author and run the activation. Navigates to the Activation canvas node (a
 * standalone page) and authors the given self-contained run script (e.g.
 * {@link dockerRunScript}) that proves the built runtime starts.
 */
export async function testActivation(page: Page, runScript: string) {
  await stepShot(page, "test-activation", "before");
  await openPort(page, "Activation");
  await expect(main(page).getByText("Activation Run Script", { exact: true })).toBeVisible();
  await saveRunScript(
    page,
    main(page).getByRole("textbox", { name: "Activation run script", exact: true }),
    runScript,
  );
  await main(page)
    .getByRole("button", { name: /Run activation/ })
    .click();
  // DinD: cold `docker load` of the runtime image + run (no shared cache).
  await expect(main(page).getByRole("button", { name: /Re-run/ })).toBeVisible({ timeout: 90000 });
  // Re-run appears for failed runs too; the earned-outcome badge is
  // success-only.
  await expect(main(page).getByRole("status", { name: "Activation passed" })).toBeVisible();
  await stepShot(page, "test-activation", "after");
}

/**
 * Define a single experiment, author its run and verify scripts, run it, and
 * wait for it to pass. Like activation, the experiment owns its full run via
 * the given script, which must tee its stdout to {@link EXPERIMENT_OUTPUT_FILE}
 * (e.g. `dockerRunScript(cmd, runtime, EXPERIMENT_OUTPUT_FILE)`). The verify
 * script owns the claim, reading that file back — its exit code is the verdict.
 */
export async function runExperiment(
  page: Page,
  experiment: {
    name: string;
    runScript: string;
    expectedStdout: string;
    /**
     * Run script inference for this experiment once it is named (the gate the
     * backend needs to resolve it) and assert it produced a scaffold, before
     * authoring the real run script over it. Returns nothing — the assertions
     * live here so the caller keeps one step.
     */
    generateFirst?: boolean;
  },
) {
  await stepShot(page, "run-experiment", "before");
  await openPort(page, "Experiments");
  const experimentsPanel = page.getByRole("region", { name: "Experiments" });
  await expect(
    experimentsPanel.getByRole("heading", { name: "Experiments", exact: true }),
  ).toBeVisible();
  // Adding the row autosaves an experiment that has no name yet, which the
  // backend cannot declare — settle that round-trip without demanding it
  // succeed, so the naming patch below is the one held to the standard.
  const experimentAdded = waitForDefinitionPatch(page, { expectOk: false });
  await experimentsPanel
    .getByRole("button", { name: /Add experiment/i })
    .first()
    .click();
  await experimentAdded;

  const nameSaved = waitForDefinitionPatch(page);
  await experimentsPanel.getByPlaceholder("smoke-test").fill(experiment.name);
  await nameSaved;

  if (experiment.generateFirst) {
    // The experiment is declared now, so inference can resolve it and the
    // already-built runtime. Phase 1 never picks the scientific command, so the
    // scaffold arrives fail-closed — the author writes the command below.
    const { message, graph, script } = await generateScript(page);
    expect(message).toMatch(/Loaded a generated experiment run script/);
    expect(graph).toContain("experiment-run-inference");
    expect(script).toMatch(/exit 64/);
  }

  // Naming the experiment already settled its reserved run-script path on the
  // intent, so this save writes the file and re-declares nothing — wait on the
  // write itself rather than an intent PATCH that legitimately never fires.
  const runScriptWritten = waitForFileWrite(page);
  await saveRunScript(
    page,
    main(page).getByRole("textbox", { name: "Experiment run script", exact: true }),
    experiment.runScript,
  );
  await runScriptWritten;

  // Same as the run script: a definition patch carries an experiment's name and
  // output paths, and nothing else — the backend reads its scripts' identities
  // off the authored files, and sees the verify script by its presence at the
  // reserved path. So this save writes a file and patches nothing; the PUT is
  // the only signal that fires.
  const verifyScriptDeclared = waitForFileWrite(page);
  await saveVerifyScript(
    page,
    main(page).getByRole("textbox", { name: "Experiment verify script", exact: true }),
    stdoutContainsVerifyScript(experiment.expectedStdout),
  );
  await verifyScriptDeclared;

  // Declare the produced result file so a successful run captures it. Including
  // it in the bundle is a seal-time choice made on the Seal page (defaults on
  // once an output is declared), so there is nothing to opt into here.
  const outputDeclared = waitForDefinitionPatch(page);
  await main(page).getByRole("textbox", { name: "Output files" }).fill(EXPERIMENT_OUTPUT_FILE);
  await outputDeclared;

  await main(page).getByRole("button", { name: /^Run$/ }).click();
  // Fail fast with a clear signal if the click was still dropped: a started
  // run flips the header button to Running…/Re-run within moments.
  await expect(main(page).getByRole("button", { name: /Running…|Re-run/ })).toBeVisible({
    timeout: 10000,
  });
  const runResult = main(page).getByRole("region", { name: "Run result" });
  // DinD: cold runtime-image load + container run on the per-REE daemon —
  // the heaviest wait in the suite, and the first to blow its budget when
  // the host is under load. Keep it roomier than the other 90s steps.
  await expect(runResult.getByText("pass", { exact: true })).toBeVisible({ timeout: 180000 });
  await expect(runResult.getByText(/declared validation passed/)).toBeVisible();
  await stepShot(page, "run-experiment", "after");
}

/**
 * The review console: the graph strip in the status bar, plus the evidence
 * drawer that strip opens beside the canvas.
 *
 * Two regions rather than one because the console is two surfaces now — the
 * strip carries the steps and their verdicts, the drawer carries what each
 * verdict rests on — and a reviewer's assertions should not have to know which
 * half a given line lives in.
 */
function reviewConsole(page: Page) {
  return page
    .getByRole("region", { name: "Workspace status" })
    .or(page.getByRole("region", { name: "Review evidence" }));
}

/**
 * Switch the persistent workflow bar to Review and open the evidence drawer.
 *
 * The drawer is opened here, once, because every lifecycle step below reads the
 * detail behind its verdict from it — and it holds the whole attempt, so it
 * fills in as the steps settle rather than needing to be reopened per step.
 */
export async function openReviewConsole(page: Page) {
  await stepShot(page, "open-review-console", "before");
  const console = reviewConsole(page);
  await console.getByRole("button", { name: "Switch to review workflow" }).click();
  await expect(console.getByRole("button", { name: "Reproduce Source" })).toBeVisible();
  await console.getByRole("button", { name: /^Open Source review evidence/ }).click();
  await expect(page.getByRole("region", { name: "Review evidence" })).toBeVisible();
  await stepShot(page, "open-review-console", "after");
  return console;
}

/**
 * Choose what the next review step reproduces from.
 *
 * "Strongest" is the default and needs no selection; "From bundle" is the
 * deliberate choice to verify the artifacts the REE already carries, which is
 * the only path open for an REE with no reachable origin.
 */
export async function selectReviewBasis(
  page: Page,
  label: "Strongest" | "Independent" | "From bundle",
) {
  await reviewConsole(page).getByRole("radio", { name: label, exact: true }).check();
}

/**
 * Run the source step of the review lifecycle and wait for its verdict.
 *
 * A review acquires the author-pinned source into its own namespace — a real
 * fetch from the recorded origin, then a SWHID over the acquired tree — so this
 * takes about as long as the author's own acquisition, plus hashing. Returns the
 * verdict the comparison settled on, as shown on the step.
 */
export async function reproduceSource(page: Page) {
  return reproduceReviewStep(page, "Source", 180000);
}

/**
 * Run the build step of the review lifecycle and wait for its verdict.
 *
 * The reviewer rebuilds the runtime from the source their own attempt fetched,
 * then scans it — a full container build plus an SBOM scan, so it is the
 * slowest step in the lifecycle. Returns the verdict the comparison settled on.
 * ``EQUIVALENT`` is the expected pass: image builds are rarely bit-identical,
 * so matching dependency closures is what a faithful rebuild earns.
 */
export async function reproduceBuild(page: Page) {
  return reproduceReviewStep(page, "Build", 600000);
}

/**
 * Run the activation step of the review lifecycle and wait for its verdict.
 *
 * Unlike source and build this settles a boolean, not a comparison: there is no
 * author artifact to diff against, so the reviewer's own probe is the claim.
 * ``COMPLETE`` means the runtime came up; ``DID NOT ACTIVATE`` means it did not,
 * which is a finding the step completed with rather than a step that broke.
 */
export async function reproduceActivation(page: Page) {
  return reproduceReviewStep(page, "Test Activation", 600000);
}

/**
 * Reproduce one named experiment and wait for the verdict its own row settles.
 *
 * Addressed by name rather than by clicking the graph node, because the
 * experiments step has one row per experiment: the node sweeps the whole set,
 * while a reviewer reproducing a single claim uses its row.
 *
 * `REPRODUCED` is the ordinary pass — the author's verify script accepted the
 * reviewer's results. `IDENTICAL` additionally means the declared outputs came
 * out byte for byte the same, which most experiments will not manage and none
 * are required to.
 */
export async function reproduceExperiment(
  page: Page,
  experimentName: string,
  timeout = 600000,
): Promise<string> {
  const console = reviewConsole(page);
  const slug = `reproduce-experiment-${experimentName.toLowerCase().replace(/\s+/g, "-")}`;
  await stepShot(page, slug, "before");
  const row = console
    .getByRole("button", { name: `Reproduce experiment ${experimentName}` })
    .locator("xpath=..");
  const verdict = row.getByText(/^(IDENTICAL|REPRODUCED|DIFFERENT|INCONCLUSIVE|FAILED)$/);
  await expect(verdict).toHaveCount(0);
  await console.getByRole("button", { name: `Reproduce experiment ${experimentName}` }).click();
  await expect(verdict).toBeVisible({ timeout });
  await stepShot(page, slug, "after");
  return (await verdict.textContent()) ?? "";
}

/** Click one review step and read back the verdict it settles on. */
async function reproduceReviewStep(page: Page, label: string, timeout: number) {
  const console = reviewConsole(page);
  const slug = `reproduce-${label.toLowerCase().replace(/\s+/g, "-")}`;
  await stepShot(page, slug, "before");
  const step = console.getByRole("button", { name: `Reproduce ${label}` });
  await expect(step).toBeEnabled();
  await step.click();
  // The run key and the verdict are separate controls on one card — reading a
  // verdict and dispatching a rebuild do not share a hitbox — so the verdict is
  // read from the card the run key sits on.
  const verdict = step
    .locator("xpath=..")
    .getByText(
      /^(IDENTICAL|EQUIVALENT|REPRODUCED|DIFFERENT|INCONCLUSIVE|COMPLETE|DID NOT ACTIVATE|FAILED)$/,
    );
  // A re-run starts from the badge the previous attempt left on the step, and
  // that stale verdict would satisfy the wait below immediately. Clicking marks
  // the step queued in the same render, so the badge clears client-side before
  // the run is even dispatched — a first run has no badge and passes straight
  // through.
  await expect(verdict).toHaveCount(0);
  await expect(verdict).toBeVisible({ timeout });
  await stepShot(page, slug, "after");
  return (await verdict.textContent()) ?? "";
}

/**
 * Seal the REE. Uses the "Seal anyway" path so it works regardless of how
 * complete the REE is — sealing is what makes the workbench release control
 * appear.
 */
/** The Seal page drawer opened from its constellation node. */
function sealPanel(page: Page) {
  return page.getByRole("region", { name: "Seal" });
}

export async function sealRee(page: Page) {
  await stepShot(page, "seal-ree", "before");
  await openPort(page, "Seal");
  const sealButton = sealPanel(page)
    .getByRole("button", { name: /Seal (REE|anyway)/ })
    .first();
  await expect(sealButton).toBeVisible();
  await sealButton.click();
  // By role rather than by text: the badge carries an icon, whose <title>
  // counts as text even though `aria-hidden` keeps it out of the name.
  await expect(sealPanel(page).getByRole("status", { name: "REE sealed" })).toBeVisible({
    timeout: 30000,
  });
  await stepShot(page, "seal-ree", "after");
}

/** Release (tear down) the workbench container; returns to the landing view. */
export async function releaseWorkbench(page: Page) {
  await stepShot(page, "release-workbench", "before");
  await openWorkbenchConsole(page);
  const releaseButton = page.getByRole("button", { name: /Release workbench/i }).first();
  await expect(releaseButton).toBeVisible();
  await releaseButton.click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: "Create a new REE" })).toBeVisible();
  await stepShot(page, "release-workbench", "after");
}

/** Open the workbench console from the persistent footer status bar. */
export async function openWorkbenchConsole(page: Page) {
  const footer = page.getByRole("region", { name: "Workbench status" });
  const trigger = footer.getByRole("button", { name: /^Workbench/ });
  if ((await trigger.getAttribute("aria-pressed")) !== "true") await trigger.click();
  await expect(page.getByRole("button", { name: "Collapse workbench console" })).toBeVisible();
}

/**
 * Best-effort teardown for the workbench container a test provisioned. Releases
 * it via the bench console. Safe to call after any test — it no-ops when no
 * provisioned session is present.
 */
export async function cleanupWorkbench(page: Page) {
  // Only meaningful inside a provisioned editor session. A test that ended back
  // on the landing view (e.g. already released) has nothing to clean up.
  if (!page.url().includes("/workspace")) {
    return;
  }

  // The Seal node is locked (disabled) until the workbench is provisioned; if it
  // isn't enabled the test never provisioned — no container to release.
  const sealNav = nav(page).getByRole("button", { name: "Seal", exact: true });
  if (!(await sealNav.isEnabled().catch(() => false))) {
    return;
  }

  await releaseWorkbench(page);
}
