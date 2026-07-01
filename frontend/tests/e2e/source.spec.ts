import { execFileSync } from "node:child_process";
import { expect, test } from "./helpers/fixtures";
import {
  downloadSource,
  provisionWorkbench,
  pythonHelloWorld,
  startReeCreation,
  uploadSource,
} from "./helpers/flow";

const GIT_ORIGIN_URL = "https://codeberg.org/vuducanh1112/repo2ree";

test.describe("Source acquisition page", () => {
  test("git origin URL is fetched into the workspace and its commit resolved", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);

    const clearSource = await downloadSource(page, { url: GIT_ORIGIN_URL, sourceType: "git" });

    await expect(clearSource).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    // The origin URL is committed into the (now locked) Source Snapshot field.
    await expect(page.getByPlaceholder("https://github.com/org/repo")).toHaveValue(GIT_ORIGIN_URL);

    // With no revision requested we fetched HEAD; acquisition settles the concrete
    // commit onto the intent and the UI surfaces it as the reproducibility receipt
    // a sealed bundle re-fetches. Backend-computed, so allow it to arrive.
    await expect(page.getByText(/Resolved to commit/)).toBeVisible({ timeout: 20000 });

    // Workspace Snapshot surfaces the backend-computed source metadata; a git
    // download reports the origin it was fetched from, not "Upload".
    const snapshot = page.getByText("Workspace Snapshot").locator("..");
    await expect(snapshot.getByText("Origin", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("Type", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("git", { exact: true })).toBeVisible();
  });

  test("uploaded tarball lands in the workspace and is browsable", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);

    const clearSource = await uploadSource(page, pythonHelloWorld());

    await expect(clearSource).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    // The archive name now appears both in the committed Source Snapshot field
    // and as the Name in the Workspace Snapshot metadata, so match the first.
    await expect(
      page.getByText("python-hello-world.tar.gz", { exact: true }).first(),
    ).toBeVisible();

    // Workspace Snapshot surfaces the backend-computed source metadata. An
    // uploaded tarball reports "Upload" as its origin and a known byte size.
    const snapshot = page.getByText("Workspace Snapshot").locator("..");
    await expect(snapshot.getByText("Origin", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("Upload", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("Size", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("python-hello-world.tar.gz", { exact: true })).toBeVisible();

    // Files are browsable from the file-tree HUD console docked on the canvas.
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Expand files" }).click();
    await expect(page.getByRole("button", { name: "Collapse files" })).toBeVisible();

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
