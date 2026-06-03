import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  main,
  provisionWorkbench,
  pythonHelloWorld,
  runExperiment,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Experiments page", () => {
  test("an experiment whose output matches the expectation passes", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());
    await buildRuntime(
      page,
      "python_hello_world/build_runtime.sh",
      "python_hello_world/runtime.tar",
    );

    await runExperiment(page, {
      name: "echo-hello",
      command: "echo hello",
      expectedStdout: "hello",
    });

    const runResult = main(page)
      .locator("div")
      .filter({ hasText: /^Run result/ })
      .first();
    await expect(runResult.getByText("pass", { exact: true })).toBeVisible();
  });
});
