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
    await buildRuntime(page, "python_hello_world", "python_hello_world/runtime.tar");

    await runExperiment(page, {
      name: "python-hello",
      command: "python python_hello_world/main.py",
      expectedStdout: "Pandas Hello World",
      runtimePath: "python_hello_world/runtime.tar",
    });

    const runResult = main(page)
      .locator("div")
      .filter({ hasText: /^Run result/ })
      .first();
    await expect(runResult.getByText("pass", { exact: true })).toBeVisible();
  });
});
