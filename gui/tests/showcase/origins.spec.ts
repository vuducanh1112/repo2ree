import { expect, test } from "../helpers/fixtures";
import {
  downloadSource,
  openReviewConsole,
  provisionWorkbench,
  reproduceSource,
  startReeCreation,
} from "../helpers/flow";
import { E2E_GIT_ORIGIN_URL, E2E_TARBALL_ORIGIN_URL } from "../helpers/origins";

test.describe("Source acquisition page", () => {
  test("git origin URL is fetched into the workspace and its commit resolved", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);

    const clearSource = await downloadSource(page, {
      url: E2E_GIT_ORIGIN_URL,
      sourceType: "git",
    });

    await expect(clearSource).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    await expect(page.getByPlaceholder("https://github.com/org/repo")).toHaveValue(
      E2E_GIT_ORIGIN_URL,
    );

    await expect(page.getByText(/Resolved to commit/)).toBeVisible({ timeout: 20000 });

    const snapshot = page.getByRole("region", { name: "Workspace Snapshot" });
    await expect(snapshot.getByText("Origin", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("Type", { exact: true })).toBeVisible();
    await expect(snapshot.getByText("git", { exact: true })).toBeVisible();
  });
});

test.describe("Tarball origin", () => {
  test("a tarball origin is fetched into the workspace", async ({ page }) => {
    test.skip(!E2E_TARBALL_ORIGIN_URL, "this stack serves no tarball origin");
    await startReeCreation(page);
    await provisionWorkbench(page);

    const clearSource = await downloadSource(page, {
      url: E2E_TARBALL_ORIGIN_URL,
      sourceType: "tarball",
    });

    await expect(clearSource).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    const snapshot = page.getByRole("region", { name: "Workspace Snapshot" });
    await expect(snapshot.getByText("tarball", { exact: true })).toBeVisible();
    await expect(snapshot.getByText(/^swh:1:dir:[0-9a-f]{40}$/)).toBeVisible({ timeout: 20000 });
  });
});

test.describe("Review source", () => {
  test("source reproduction re-fetches the pinned origin and reports identical", async ({
    page,
  }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await downloadSource(page, { url: E2E_GIT_ORIGIN_URL, sourceType: "git" });
    await expect(page.getByText(/Resolved to commit/)).toBeVisible({ timeout: 20000 });
    await expect(
      page
        .getByRole("region", { name: "Workspace Snapshot" })
        .getByText(/^swh:1:dir:[0-9a-f]{40}$/),
    ).toBeVisible({ timeout: 20000 });

    const review = await openReviewConsole(page);
    await expect(review.getByText("Not reproduced yet.").first()).toBeVisible();
    await expect(
      review.getByRole("button", { name: "Reproduce Build Experiment Environment" }),
    ).toBeDisabled();

    expect(await reproduceSource(page)).toBe("IDENTICAL");

    await expect(
      review.getByRole("button", { name: /^Open Source review evidence, identical/ }),
    ).toBeVisible();
    await expect(
      review.getByRole("button", { name: "Reproduce Build Experiment Environment" }),
    ).toBeEnabled();
    await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeDisabled();
    await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeDisabled();
  });
});
