import { expect, test } from "./helpers/fixtures";
import {
  main,
  provideHbom,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Hardware BOM page", () => {
  test("a CPU component card keeps the entered device model", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    await provideHbom(page, "Intel Core i9-14900K");

    await expect(main(page).getByPlaceholder("Intel Core i9-14900K").first()).toHaveValue(
      "Intel Core i9-14900K",
    );
  });
});
