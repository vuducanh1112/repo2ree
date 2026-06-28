import { expect, test } from "./helpers/fixtures";
import {
  buildRuntime,
  generateSbom,
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
    await buildRuntime(page, "python_hello_world", "python_hello_world/runtime.tar");

    await generateSbom(page);

    await expect(
      page
        .getByRole("region", { name: "Generate SBOM" })
        .getByText("SBOM ready", { exact: true })
        .first(),
    ).toBeVisible();
  });
});
