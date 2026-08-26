import { expect, test } from "@playwright/test";
import { openVisualWorkspace } from "../gui-page-scenarios/page";
import { installVisualScenario } from "../gui-page-scenarios/scenario";

const OUT =
  "/tmp/nix-shell.62pIha/claude-1000/-repo2ree/97227911-b099-4b15-9df4-5c810668ac54/scratchpad";

test("scene", async ({ page }) => {
  await installVisualScenario(page);
  await openVisualWorkspace(page);
  await page.screenshot({ path: `${OUT}/scene.png` });
  expect(true).toBe(true);
});
