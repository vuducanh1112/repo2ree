import { expect, test } from "../e2e/helpers/fixtures";
import {
  buildRuntime,
  INSTANT_RUNTIME_PATH,
  instantHelloWorld,
  instantRecipe,
  LIGHTWEIGHT_WORKBENCH_IMAGE,
  main,
  provisionWorkbench,
  releaseWorkbench,
  runBuild,
  runEvaluate,
  startReeCreation,
  uploadSource,
} from "../e2e/helpers/flow";
import { stepShot } from "../screenshot";
import { keepReeArchive } from "./keepArchive";

const FAILING_BUILD = `#!/usr/bin/env sh
set -eu
echo 'resolving dependencies'
exit 3
`;

/**
 * How the author sees a stage fail, and recovers: the failure and its log are
 * on screen, no success badge is earned, and fixing the script builds the same
 * REE. The fault matrix itself lives in the system suite (api/tests/system);
 * this spec covers what the GUI shows.
 */
test.describe("Instant failures", () => {
  test("a failing build is shown with its log, and a fixed script builds", async ({ page }) => {
    await test.step("provision and upload", async () => {
      await startReeCreation(page);
      await provisionWorkbench(page, { imageRef: LIGHTWEIGHT_WORKBENCH_IMAGE });
      await uploadSource(page, instantHelloWorld());
      await runEvaluate(page);
    });

    await test.step("a build script that exits 3", async () => {
      await stepShot(page, "failing-build", "before");
      await runBuild(page, FAILING_BUILD, INSTANT_RUNTIME_PATH);
      await expect(main(page).getByRole("status", { name: "Built" })).toHaveCount(0);
      await expect(main(page).getByText("resolving dependencies").first()).toBeVisible();
      await stepShot(page, "failing-build", "after");
    });

    await test.step("the fixed script builds", async () => {
      await buildRuntime(page, instantRecipe("build_script.sh"), INSTANT_RUNTIME_PATH, {
        rebuild: true,
      });
    });

    await test.step("keep the REE and release", async () => {
      await keepReeArchive(page);
      await releaseWorkbench(page);
    });
  });
});
