import { expect, test } from "@playwright/test";
import { applicationPageScenarios } from "../gui-page-scenarios/applicationPages";
import { installVisualScenario } from "../gui-page-scenarios/scenario";

test.beforeEach(async ({ page }) => {
  await installVisualScenario(page);
});

for (const scenario of applicationPageScenarios) {
  test(scenario.name, async ({ page }) => {
    await scenario.prepare(page);
    await expect(page).toHaveScreenshot(scenario.screenshot);
  });
}
