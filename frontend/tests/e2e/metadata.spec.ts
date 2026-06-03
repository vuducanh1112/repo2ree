import { expect, test } from "./helpers/fixtures";
import {
  provideMetadata,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Metadata page", () => {
  test("identity fields persist what was entered", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    await provideMetadata(page, {
      name: "ree-hello-world",
      version: "1.0.0",
      description: "A reusable execution environment for the Python hello world archive.",
    });

    await expect(page.getByPlaceholder("deepfold-protein-structure-prediction")).toHaveValue(
      "ree-hello-world",
    );
    await expect(page.getByPlaceholder("1.0.0")).toHaveValue("1.0.0");
    await expect(page.getByPlaceholder("REE for reproducible execution of...")).toHaveValue(
      "A reusable execution environment for the Python hello world archive.",
    );
  });
});
