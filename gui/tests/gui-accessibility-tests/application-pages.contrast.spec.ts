import { test } from "@playwright/test";
import { applicationPageScenarios } from "../gui-page-scenarios/applicationPages";
import { installVisualScenario } from "../gui-page-scenarios/scenario";
import { expectPageToMeetContrast } from "./contrast";

test.beforeEach(async ({ page }) => {
  await installVisualScenario(page);
});

for (const scenario of applicationPageScenarios) {
  test(scenario.name, async ({ page }, testInfo) => {
    await scenario.prepare(page);
    await expectPageToMeetContrast(page, testInfo, scenario.contrastRoot);
  });
}

test("semantic text roles", async ({ page }, testInfo) => {
  await page.goto("/");
  await page.evaluate(() => {
    const pairs = [
      ["--chrome-text-muted", "--chrome-surface"],
      ["--chrome-text-muted", "--chrome-bg"],
      ["--ink-subtle", "--palette-white"],
      ["--tone-success-ink", "--tone-success-surface"],
      ["--tone-warning-ink", "--tone-warning-surface"],
      ["--threat-medium-line", "--threat-medium-wash"],
      // Every stage's badge text on its own wash. Scanned here rather than only
      // where a page happens to render one: five stages carry an outcome badge
      // today, and the pairing was wrong for two of them before anyone looked.
      ...[
        "source",
        "metadata",
        "hbom",
        "experiments",
        "evaluate",
        "build",
        "sbom",
        "activation",
        "archive",
        "seal",
      ].map((stage) => [`--stage-${stage}-ink`, `--stage-${stage}-wash`]),
    ];
    const matrix = document.createElement("div");
    matrix.id = "contrast-token-matrix";
    for (const [foreground, background] of pairs) {
      const sample = document.createElement("div");
      sample.textContent = `${foreground} on ${background}`;
      sample.style.color = `var(${foreground})`;
      sample.style.background = `var(${background})`;
      sample.style.fontSize = "13px";
      matrix.append(sample);
    }
    document.body.append(matrix);
  });
  await expectPageToMeetContrast(page, testInfo, "#contrast-token-matrix");
});
