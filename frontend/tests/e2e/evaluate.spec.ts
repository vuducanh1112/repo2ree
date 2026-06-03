import { expect, test } from "./helpers/fixtures";
import {
  main,
  provisionWorkbench,
  pythonHelloWorld,
  runEvaluate,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Evaluate page", () => {
  test("running evaluation produces a reproducibility score", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    await runEvaluate(page);

    await expect(main(page).getByRole("button", { name: /Re-run Evaluate/ })).toBeVisible();
  });
});
