import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  main,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Runtime Environment page", () => {
  test("building and including the runtime activates the Runtime cable", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    await buildRuntime(
      page,
      "python_hello_world/build_runtime.sh",
      "python_hello_world/runtime.tar",
    );

    await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible();
  });
});
