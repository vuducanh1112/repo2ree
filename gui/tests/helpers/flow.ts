import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, type Locator, type Page, test } from "@playwright/test";
import { FIXTURES_DIR } from "../artifacts";
import { NETWORK_RUN, quiet, runToEnd, type SettleOptions, StartedRuns, settleRun } from "../runs";
import { stepShot } from "../screenshot";

const EXAMPLES_DIR = path.resolve(__dirname, "../../../examples");

export function pythonHelloWorld(): string {
  return packedProject("python_docker");
}

export function authoredRee(): string {
  return path.join(EXAMPLES_DIR, "rees/ree-hello-world.zip");
}

export function pythonPipHelloWorld(): string {
  return packedProject("python_venv");
}

export const INSTANT_EXPERIMENT_ENVIRONMENT_PATH = "source/runtime-venv.tar.gz";

export function instantHelloWorld(): string {
  return packedProject("instant");
}

export const INSTANT_DOCKER_EXPERIMENT_ENVIRONMENT_PATH = "source/runtime-image.tar";

export function instantDockerHelloWorld(): string {
  return packedProject("instant_docker");
}

type ExampleProject = "instant" | "instant_docker" | "java_maven" | "python_docker" | "python_venv";

export function packedProject(project: ExampleProject): string {
  mkdirSync(FIXTURES_DIR, { recursive: true });
  const archive = path.join(FIXTURES_DIR, `${project.replaceAll("_", "-")}.tar.gz`);
  execFileSync("tar", [
    "-czf",
    archive,
    "--exclude=__pycache__",
    "-C",
    path.join(EXAMPLES_DIR, "projects", project),
    "source",
  ]);
  return archive;
}

export function instantRecipe(
  name: "build_experiment_environment.sh" | "activate_experiment_environment.sh" | "experiment.sh",
  project: "instant" | "instant_docker" = "instant",
): string {
  return readFileSync(path.join(EXAMPLES_DIR, "projects", project, "recipe", name), "utf8");
}

export function dockerActivateScript(
  experimentEnvironmentPath: string,
  imageName = "pandas-hello",
): string {
  return `#!/usr/bin/env sh
set -eu

IMAGE=${JSON.stringify(`${imageName}:latest`)}
EXPERIMENT_ENVIRONMENT_FILE=${JSON.stringify(experimentEnvironmentPath)}

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker load < "$EXPERIMENT_ENVIRONMENT_FILE"
exec docker run --rm -v "$PWD:$PWD" -w "$PWD" --entrypoint "" "$IMAGE" "$@"
`;
}

export function commandScript(command: string, outputFile?: string): string {
  const capture = outputFile ? ` > ${JSON.stringify(outputFile)}` : "";
  const replay = outputFile ? `\ncat ${JSON.stringify(outputFile)}` : "";
  return `#!/usr/bin/env sh
set -eu

${command}${capture}${replay}
`;
}

export async function saveActivateScript(page: Page, script: string) {
  await openPort(page, "Build Experiment Environment");
  await page.getByLabel("Activate experiment environment script").fill(script);
  const saved = waitForFileWrite(page);
  await main(page).getByRole("button", { name: "Save activate script" }).click();
  await saved;
}

export const EXPERIMENT_OUTPUT_FILE = "result.txt";

export function main(page: Page) {
  return page.getByRole("main");
}

const GENERATE_STATUS = /Loaded a generated|could be inferred yet|Generation failed/;

export async function generateScript(
  page: Page,
  button: RegExp = /Generate from repository/,
): Promise<{ message: string; graph: string; script: string }> {
  await stepShot(page, "generate-script", "before");
  const content = main(page);
  const trigger = content.getByRole("button", { name: button }).first();
  const control = trigger.locator("xpath=../..");
  const [response] = await Promise.all([
    page.waitForResponse(
      (candidate) =>
        candidate.url().includes("suggest-scripts") && candidate.request().method() === "POST",
      { timeout: 30000 },
    ),
    trigger.click(),
  ]);
  const report = (await response.json()) as {
    results?: { candidates?: { body?: string | null }[] }[];
  };
  const script = report.results?.[0]?.candidates?.[0]?.body ?? "";

  const status = control.getByText(GENERATE_STATUS).first();
  await expect(status).toBeVisible({ timeout: 30000 });
  const message = (await status.textContent()) ?? "";

  const summary = control.getByText("Decision graph", { exact: true }).first();
  await expect(summary).toBeVisible();
  await summary.click();
  const graphBlock = control
    .locator("details")
    .filter({ hasText: "Decision graph" })
    .locator("pre")
    .first();
  await expect(graphBlock).toBeVisible();
  const graph = (await graphBlock.textContent()) ?? "";

  await stepShot(page, "generate-script", "after");
  return { message, graph, script };
}

async function waitForDefinitionPatch(
  page: Page,
  { expectOk = true, carrying }: { expectOk?: boolean; carrying?: string } = {},
) {
  const response = await page.waitForResponse(
    (res) =>
      res.url().includes("/patch-ree-definition") &&
      res.request().method() === "POST" &&
      (carrying === undefined ||
        (res.request().postData() ?? "").includes(JSON.stringify(carrying))),
  );
  if (expectOk && !response.ok()) {
    throw new Error(
      `definition patch rejected with ${response.status()}: ${await response.text()}`,
    );
  }
  return response;
}

function waitForFileWrite(page: Page) {
  return page.waitForResponse(
    (res) => res.url().includes("/write-script") && res.request().method() === "POST",
  );
}

function nav(page: Page) {
  return page.getByRole("navigation", { name: "Workspace pages" });
}

export async function openPort(page: Page, label: string) {
  await nav(page).getByRole("button", { name: label, exact: true }).click();
}

export async function openFilesConsole(page: Page) {
  const status = page.getByRole("region", { name: "Workspace status" });
  const trigger = status.getByRole("button", { name: /^Files/ });
  if ((await trigger.getAttribute("aria-pressed")) !== "true") await trigger.click();
  await expect(page.getByRole("button", { name: "Collapse files" })).toBeVisible();
}

const AVAILABLE_LAB = /— available$/;

export async function connectedLabCount(page: Page): Promise<number> {
  await page.goto("/");
  await page.getByRole("button", { name: "Create a new REE" }).click();
  await expect(page.getByRole("heading", { name: "Where should this REE run?" })).toBeVisible();
  const cards = page.getByRole("button", { name: AVAILABLE_LAB });
  await cards.first().waitFor({ state: "visible" });
  return cards.count();
}

export async function startReeCreation(page: Page, options?: { labIndex?: number }) {
  await page.goto("/");
  await stepShot(page, "start-ree-creation", "before");
  await page.getByRole("button", { name: "Create a new REE" }).click();
  await expect(page.getByRole("heading", { name: "Where should this REE run?" })).toBeVisible();
  await page
    .getByRole("button", { name: AVAILABLE_LAB })
    .nth(options?.labIndex ?? 0)
    .click();
  await expect(page.getByRole("region", { name: "Set up the workbench" })).toBeVisible();
  await stepShot(page, "start-ree-creation", "after");
  return (await page.locator("[data-lab][aria-pressed='true']").getAttribute("data-lab")) ?? "";
}

export async function provisionWorkbench(page: Page) {
  await stepShot(page, "provision-workbench", "before");
  const setup = page.getByRole("region", { name: "Set up the workbench" });
  await runToEnd(page, () => setup.getByRole("button", { name: /Provision workbench/i }).click(), {
    watch: NETWORK_RUN,
    succeed: true,
  });
  await expect(nav(page).getByRole("button", { name: "Source", exact: true })).toBeVisible();
  await openPort(page, "Source");
  await expect(
    page.getByRole("region", { name: "Source Acquisition" }).getByText("Source Acquisition", {
      exact: true,
    }),
  ).toBeVisible();
  await stepShot(page, "provision-workbench", "after");
}

export async function provisionFromBundle(page: Page, bundlePath: string) {
  await stepShot(page, "provision-from-bundle", "before");
  await page.getByLabel("REE bundle").setInputFiles(bundlePath);
  await expect(page.getByText(/This workbench will be loaded with the uploaded REE/)).toBeVisible();
  const runs = new StartedRuns(page);
  try {
    await page.getByRole("button", { name: /Provision and load REE/i }).click();
    await settleRun(page, await runs.next(), { watch: NETWORK_RUN, succeed: true });
    await settleRun(page, await runs.next(), { watch: NETWORK_RUN, succeed: true });
  } finally {
    runs.stop();
  }
  await expect(nav(page).getByRole("button", { name: "Source", exact: true })).toBeVisible();
  await stepShot(page, "provision-from-bundle", "after");
}

export async function uploadSource(page: Page, archivePath: string) {
  await stepShot(page, "upload-source", "before");
  await page.getByRole("button", { name: "Upload tarball" }).click();
  await page
    .locator('input[type="file"][accept=".zip,.tar,.gz,.tgz,.tar.gz"]')
    .setInputFiles(archivePath);
  await runToEnd(page, () => page.getByRole("button", { name: /Add to workspace/i }).click(), {
    succeed: true,
  });

  const clearSource = page
    .getByRole("region", { name: "Source Acquisition" })
    .getByRole("button", { name: /Clear source/i });
  await expect(clearSource).toBeVisible();
  await stepShot(page, "upload-source", "after");
  return clearSource;
}

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
  await runToEnd(
    page,
    () => region.getByRole("button", { name: /Download source to workspace/i }).click(),
    { succeed: true },
  );
  const clearSource = region.getByRole("button", { name: /Clear source/i });
  await expect(clearSource).toBeVisible();
  await stepShot(page, "download-source", "after");
  return clearSource;
}

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

export async function runEvaluate(page: Page) {
  await stepShot(page, "run-evaluate", "before");
  await openPort(page, "Reproducibility Readiness");
  await expect(
    main(page).getByRole("heading", { name: "Reproducibility Readiness", exact: true }),
  ).toBeVisible();
  await runToEnd(
    page,
    () =>
      main(page)
        .getByRole("button", { name: /^Run Evaluate$/ })
        .click(),
    { succeed: true },
  );
  await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible();
  await stepShot(page, "run-evaluate", "after");
}

export function dockerBuildExperimentEnvironmentScript(
  projectDir: string,
  producedExperimentEnvironmentPath: string,
  imageName = "pandas-hello",
): string {
  return `#!/usr/bin/env sh
set -eu

IMAGE_NAME=${JSON.stringify(imageName)}
TAG="latest"
PROJECT_DIR=${JSON.stringify(projectDir)}
EXPERIMENT_ENVIRONMENT_FILE=${JSON.stringify(producedExperimentEnvironmentPath)}

docker build -t "$IMAGE_NAME:$TAG" "$PROJECT_DIR"
docker save "$IMAGE_NAME:$TAG" -o "$EXPERIMENT_ENVIRONMENT_FILE"
`;
}

export async function buildExperimentEnvironment(
  page: Page,
  buildExperimentEnvironmentScript: string,
  producedExperimentEnvironmentPath: string,
  options: { rebuild?: boolean } = {},
) {
  await stepShot(page, "build-experiment-environment", "before");
  await runBuild(page, buildExperimentEnvironmentScript, producedExperimentEnvironmentPath, {
    ...options,
    succeed: true,
  });
  await expect(main(page).getByRole("status", { name: "Built" })).toBeVisible();
  await stepShot(page, "build-experiment-environment", "after");
}

export async function runBuild(
  page: Page,
  buildExperimentEnvironmentScript: string,
  producedExperimentEnvironmentPath: string,
  { rebuild = false, succeed = false }: { rebuild?: boolean; succeed?: boolean } = {},
) {
  await openPort(page, "Build Experiment Environment");
  await expect(
    main(page).getByRole("heading", { name: "Build Experiment Environment", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Build experiment environment script")
    .fill(buildExperimentEnvironmentScript);
  const scriptSaved = waitForFileWrite(page);
  await main(page).getByRole("button", { name: "Save build script" }).click();
  await scriptSaved;

  if (!rebuild) await declareExperimentEnvironmentArtifact(page, producedExperimentEnvironmentPath);

  const run = await runToEnd(
    page,
    () =>
      main(page)
        .getByRole("button", { name: rebuild ? /Re-build/ : /Run build/ })
        .click(),
    { succeed },
  );
  await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible();
  return run;
}

async function saveRunScript(page: Page, editor: Locator, content: string) {
  await editor.fill(content);
  await main(page).getByRole("button", { name: "Save run script", exact: true }).first().click();
}

async function saveVerifyScript(page: Page, editor: Locator, content: string) {
  await editor.fill(content);
  await main(page).getByRole("button", { name: "Save verify script", exact: true }).first().click();
}

function stdoutContainsVerifyScript(expectedStdout: string): string {
  return `#!/usr/bin/env sh
set -eu

# The run script materialized its stdout to this workspace file; read it back.
EXPECTED=${JSON.stringify(expectedStdout)}
grep -Fq "$EXPECTED" ${JSON.stringify(EXPERIMENT_OUTPUT_FILE)}
`;
}

async function declareExperimentEnvironmentArtifact(
  page: Page,
  producedExperimentEnvironmentPath: string,
) {
  const experimentEnvironmentDeclared = waitForDefinitionPatch(page, {
    carrying: producedExperimentEnvironmentPath,
  });
  await page
    .getByRole("region", { name: "Experiment environment artifact" })
    .getByRole("textbox")
    .fill(producedExperimentEnvironmentPath);
  await experimentEnvironmentDeclared;
}

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

export const SBOM_ARTIFACT_PATH = "artifacts/sbom.json";

export async function generateSbom(page: Page) {
  await stepShot(page, "generate-sbom", "before");
  await openPort(page, "SBOM");
  const content = main(page);
  await expect(content.getByRole("button", { name: /^Generate$/ })).toBeVisible();
  await runToEnd(page, () => content.getByRole("button", { name: /^Generate$/ }).click(), {
    watch: quiet(),
    succeed: true,
  });
  await expect(content.getByRole("button", { name: /^Regenerate$/ })).toBeVisible();
  await expect(content.getByText("SBOM ready", { exact: true }).first()).toBeVisible();
  await expect(content.getByText(SBOM_ARTIFACT_PATH, { exact: true }).first()).toBeVisible();
  await stepShot(page, "generate-sbom", "after");
}

export async function crossCheckSbom(page: Page) {
  await stepShot(page, "cross-check-sbom", "before");
  await openPort(page, "SBOM");
  const content = main(page);
  await expect(content.getByRole("button", { name: /^Cross-check$/ })).toBeEnabled({
    timeout: 20000,
  });
  await runToEnd(page, () => content.getByRole("button", { name: /^Cross-check$/ }).click(), {
    succeed: true,
  });
  await expect(content.getByRole("button", { name: /^Re-check$/ })).toBeVisible();
  await expect(content.getByText("Cross-checked", { exact: true })).toBeVisible();
  await expect(content.getByText(/declared deps in experiment environment/)).toBeVisible();
  await stepShot(page, "cross-check-sbom", "after");
}

export async function activateExperimentEnvironment(page: Page) {
  await stepShot(page, "activate-experiment-environment", "before");
  await openPort(page, "Activation");
  await expect(main(page).getByText("What Runs", { exact: true })).toBeVisible();
  await expect(main(page).getByText(/activate_experiment_environment\.sh true/)).toBeVisible();
  await runToEnd(page, () =>
    main(page)
      .getByRole("button", { name: /Run activation/ })
      .click(),
  );
  await expect(main(page).getByRole("button", { name: /Re-run/ })).toBeVisible();
  await expect(main(page).getByRole("status", { name: "Activation passed" })).toBeVisible();
  await stepShot(page, "activate-experiment-environment", "after");
}

export async function runExperiment(
  page: Page,
  experiment: {
    name: string;
    runScript: string;
    expectedStdout: string;
    generateFirst?: boolean;
  },
) {
  await stepShot(page, "run-experiment", "before");
  await openPort(page, "Experiments");
  const experimentsPanel = page.getByRole("region", { name: "Experiments" });
  await expect(
    experimentsPanel.getByRole("heading", { name: "Experiments", exact: true }),
  ).toBeVisible();
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
    const { message, graph, script } = await generateScript(page);
    expect(message).toMatch(/Loaded a generated experiment run script/);
    expect(graph).toContain("experiment-run-inference");
    expect(script).toMatch(/exit 64/);
  }

  const runScriptWritten = waitForFileWrite(page);
  await saveRunScript(
    page,
    main(page).getByRole("textbox", { name: "Experiment run script", exact: true }),
    experiment.runScript,
  );
  await runScriptWritten;

  const verifyScriptDeclared = waitForFileWrite(page);
  await saveVerifyScript(
    page,
    main(page).getByRole("textbox", { name: "Experiment verify script", exact: true }),
    stdoutContainsVerifyScript(experiment.expectedStdout),
  );
  await verifyScriptDeclared;

  const outputDeclared = waitForDefinitionPatch(page);
  await main(page).getByRole("textbox", { name: "Output files" }).fill(EXPERIMENT_OUTPUT_FILE);
  await outputDeclared;

  await runToEnd(page, () => main(page).getByRole("button", { name: /^Run$/ }).click(), {
    succeed: true,
  });
  const runResult = main(page).getByRole("region", { name: "Run result" });
  await expect(runResult.getByText("pass", { exact: true })).toBeVisible();
  await expect(runResult.getByText(/declared validation passed/)).toBeVisible();
  await stepShot(page, "run-experiment", "after");
}

function reviewConsole(page: Page) {
  return page
    .getByRole("region", { name: "Workspace status" })
    .or(page.getByRole("region", { name: "Review evidence" }));
}

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

export async function selectReviewBasis(
  page: Page,
  label: "Strongest" | "Independent" | "From bundle",
) {
  await reviewConsole(page).getByRole("radio", { name: label, exact: true }).check();
}

export async function reproduceSource(page: Page) {
  return reproduceReviewStep(page, "Source");
}

export async function reproduceBuild(page: Page) {
  return reproduceReviewStep(page, "Build Experiment Environment", { watch: quiet() });
}

export async function reproduceActivation(page: Page) {
  return reproduceReviewStep(page, "Test Activation");
}

export async function reproduceExperiment(page: Page, experimentName: string): Promise<string> {
  const console = reviewConsole(page);
  const slug = `reproduce-experiment-${experimentName.toLowerCase().replace(/\s+/g, "-")}`;
  await stepShot(page, slug, "before");
  const row = console
    .getByRole("button", { name: `Reproduce experiment ${experimentName}` })
    .locator("xpath=..");
  const verdict = row.getByText(/^(IDENTICAL|REPRODUCED|DIFFERENT|INCONCLUSIVE|FAILED)$/);
  await expect(verdict).toHaveCount(0);
  await runToEnd(page, () =>
    console.getByRole("button", { name: `Reproduce experiment ${experimentName}` }).click(),
  );
  await expect(verdict).toBeVisible();
  await stepShot(page, slug, "after");
  return (await verdict.textContent()) ?? "";
}

async function reproduceReviewStep(page: Page, label: string, options: SettleOptions = {}) {
  const console = reviewConsole(page);
  const slug = `reproduce-${label.toLowerCase().replace(/\s+/g, "-")}`;
  await stepShot(page, slug, "before");
  const step = console.getByRole("button", { name: `Reproduce ${label}` });
  await expect(step).toBeEnabled();
  const verdict = step
    .locator("xpath=..")
    .getByText(
      /^(IDENTICAL|EQUIVALENT|REPRODUCED|DIFFERENT|INCONCLUSIVE|COMPLETE|DID NOT ACTIVATE|FAILED)$/,
    );
  await runToEnd(
    page,
    async () => {
      await step.click();
      await expect(verdict).toHaveCount(0);
    },
    options,
  );
  await expect(verdict).toBeVisible();
  await stepShot(page, slug, "after");
  return (await verdict.textContent()) ?? "";
}

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
  await runToEnd(page, () => sealButton.click(), { succeed: true });
  await expect(sealPanel(page).getByRole("status", { name: "REE sealed" })).toBeVisible();
  await stepShot(page, "seal-ree", "after");
}

const keptPages = new WeakSet<Page>();

export async function keepReeArchive(page: Page, name = "ree.zip") {
  await stepShot(page, "download-ree", "before");
  const download = page.getByRole("banner").getByRole("button", { name: /Download REE/ });
  await expect(download).toBeEnabled();
  const [file] = await Promise.all([
    page.waitForEvent("download", { timeout: 120_000 }),
    download.click(),
  ]);
  let target = test.info().outputPath(name);
  for (let copy = 2; existsSync(target); copy += 1) {
    target = test.info().outputPath(name.replace(/(\.zip)?$/, `-${copy}$1`));
  }
  await file.saveAs(target);
  keptPages.add(page);
  await stepShot(page, "download-ree", "after");
  return target;
}

export async function releaseWorkbench(page: Page) {
  if (!keptPages.has(page)) {
    await keepReeArchive(page).catch((error: unknown) => {
      test.info().annotations.push({
        type: "warning",
        description: `released without keeping the REE's archive: ${String(error)}`,
      });
    });
  }
  await stepShot(page, "release-workbench", "before");
  await openWorkbenchConsole(page);
  const deleteButton = page.getByRole("button", { name: /Delete REE$/ });
  await expect(deleteButton).toBeVisible();
  await deleteButton.click();
  await page.getByRole("button", { name: /Confirm: delete this REE$/ }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: "Create a new REE" })).toBeVisible();
  await stepShot(page, "release-workbench", "after");
}

async function openWorkbenchConsole(page: Page) {
  const footer = page.getByRole("region", { name: "Workbench status" });
  const trigger = footer.getByRole("button", { name: /^Workbench/ });
  if ((await trigger.getAttribute("aria-pressed")) !== "true") await trigger.click();
  await expect(page.getByRole("button", { name: "Collapse workbench console" })).toBeVisible();
}

export async function cleanupWorkbench(page: Page) {
  if (!page.url().includes("/workspace")) {
    return;
  }

  const sealNav = nav(page).getByRole("button", { name: "Seal", exact: true });
  if (!(await sealNav.isEnabled().catch(() => false))) {
    return;
  }

  await releaseWorkbench(page);
}
