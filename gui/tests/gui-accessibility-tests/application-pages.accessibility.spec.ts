import { test } from "@playwright/test";
import { applicationPageScenarios } from "../gui-page-scenarios/applicationPages";
import { installVisualScenario } from "../gui-page-scenarios/scenario";
import { expectPageToMeetAccessibilityStandards } from "./accessibility";

test.beforeEach(async ({ page }) => {
  await installVisualScenario(page);
});

for (const scenario of applicationPageScenarios) {
  test(`${scenario.name} meets accessibility standards`, async ({ page }, testInfo) => {
    await scenario.prepare(page);
    await expectPageToMeetAccessibilityStandards(page, testInfo);
  });
}
