import { execFileSync } from "node:child_process";
import { expect, test } from "./helpers/fixtures";
import {
  main,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

test.describe("Source acquisition page", () => {
  test("uploaded tarball lands in the workspace and is browsable", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);

    const workspaceActions = await uploadSource(page, pythonHelloWorld());

    await expect(
      workspaceActions.getByRole("button", { name: /Clear workspace source/i }),
    ).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    await expect(page.getByText("python-hello-world.tar.gz", { exact: true })).toBeVisible();

    await workspaceActions.getByRole("button", { name: /Browse workspace files/i }).click();
    await expect(main(page).getByText("Files", { exact: true })).toBeVisible();

    const archiveNodeNames = [
      ...new Set(
        execFileSync("tar", ["-tzf", pythonHelloWorld()], { encoding: "utf8" })
          .split("\n")
          .map((entry) => entry.trim())
          .filter(Boolean)
          .map((entry) => entry.replace(/\/+$/, "").split("/").filter(Boolean).pop())
          .filter((name): name is string => Boolean(name)),
      ),
    ];
    await page.getByPlaceholder("Filter files…").fill("workspace");
    for (const nodeName of archiveNodeNames) {
      const escaped = nodeName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      await expect(page.getByRole("button", { name: new RegExp(escaped) })).toBeVisible();
    }
  });
});
