import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  generateSbom,
  main,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Generate SBOM page", () => {
  test("scanning the runtime produces a ready SBOM", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());
    await buildRuntime(
      page,
      "python_hello_world/build_runtime.sh",
      "python_hello_world/runtime.tar",
    );

    await generateSbom(page);

    await expect(main(page).getByText("SBOM ready", { exact: true }).first()).toBeVisible();
  });
});
