import { expect, test } from "./helpers/fixtures";
import {
  main,
  provisionWorkbench,
  pythonHelloWorld,
  sealRee,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Seal page", () => {
  test("sealing produces a downloadable REE package", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    await sealRee(page);

    const downloadButton = main(page)
      .getByRole("button", { name: /Download REE/ })
      .first();
    await expect(downloadButton).toBeVisible();
    const [download] = await Promise.all([page.waitForEvent("download"), downloadButton.click()]);
    expect(download.suggestedFilename()).toMatch(/\.zip$/i);
  });
});
