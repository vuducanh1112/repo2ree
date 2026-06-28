import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  main,
  openPort,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Build Runtime page", () => {
  test("building and including the runtime marks the Build node done", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    await buildRuntime(page, "python_hello_world", "python_hello_world/runtime.tar");

    // buildRuntime leaves the Build page docked; re-open the Build node to
    // confirm the build persisted as a completed (re-buildable) run.
    await openPort(page, "Build");
    await expect(main(page).getByRole("button", { name: /Re-build/ })).toBeVisible();
  });
});
