import { expect, test } from "./helpers/fixtures";
import { main, provisionWorkbench, startReeCreation } from "./helpers/flow";

test.describe("Workbench lab", () => {
  test("provisioning reveals source acquisition", async ({ page }) => {
    await startReeCreation(page);
    await expect(page.getByRole("heading", { name: "Set up the workbench" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Provision workbench/i })).toBeVisible();

    await provisionWorkbench(page);

    await expect(main(page).getByText("Source Acquisition", { exact: true })).toBeVisible();
  });
});
