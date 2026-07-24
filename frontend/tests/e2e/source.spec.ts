import { expect, test } from "./helpers/fixtures";
import { downloadSource, provisionWorkbench, startReeCreation } from "./helpers/flow";

const GIT_ORIGIN_URL = "https://github.com/vuducanh1112/repo2ree.git";

// The upload path is covered by the golden-path journey (ree-pipeline.spec.ts).
// This spec keeps the branch the journey cannot take: fetching from an origin
// URL locks the source configuration, so it needs its own fresh workbench.
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
    const snapshot = page.getByRole("region", { name: "Workspace Snapshot" });
    await expect(snapshot.getByText("Origin", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("Type", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("git", { exact: true })).toBeVisible();
  });
});
