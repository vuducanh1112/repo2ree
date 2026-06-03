import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  main,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  testActivation,
  uploadSource,
} from "./helpers/flow";

test.describe("Test Activation page", () => {
  test("running the activation script completes the activation step", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());
    await buildRuntime(
      page,
      "python_hello_world/build_runtime.sh",
      "python_hello_world/runtime.tar",
    );

    await testActivation(page, "python_hello_world/activate_runtime.sh");

    await expect(main(page).getByRole("button", { name: /Re-run/ })).toBeVisible();
  });
});
