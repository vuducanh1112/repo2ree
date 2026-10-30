import { expect, test } from "../helpers/fixtures";
import {
  downloadSource,
  LIGHTWEIGHT_WORKBENCH_IMAGE,
  openReviewConsole,
  provisionWorkbench,
  reproduceSource,
  startReeCreation,
} from "../helpers/flow";
import { E2E_GIT_ORIGIN_URL, E2E_TARBALL_ORIGIN_URL } from "../helpers/origins";

/**
 * Sources fetched from an origin URL rather than uploaded: by git and as a
 * tarball, and fetched again by a reviewer. The upload path is the other
 * scenarios'. Fetching locks the source configuration, so each case needs a
 * fresh workbench of its own. The stack serves the origins itself
 * (repo2ree_testbed.stack.origins): the same commit and bytes on every run.
 */

test.describe("Source acquisition page", () => {
  test("git origin URL is fetched into the workspace and its commit resolved", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page, { imageRef: LIGHTWEIGHT_WORKBENCH_IMAGE });

    const clearSource = await downloadSource(page, {
      url: E2E_GIT_ORIGIN_URL,
      sourceType: "git",
    });

    await expect(clearSource).toBeVisible();
    await expect(page.getByText(/Configuration locked/)).toBeVisible();
    // The origin URL is committed into the (now locked) Source Snapshot field.
    await expect(page.getByPlaceholder("https://github.com/org/repo")).toHaveValue(
      E2E_GIT_ORIGIN_URL,
    );

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

test.describe("Tarball origin", () => {
  test("a tarball origin is fetched into the workspace", async ({ page }) => {
    test.skip(!E2E_TARBALL_ORIGIN_URL, "this stack serves no tarball origin");
    await startReeCreation(page);
    await provisionWorkbench(page, { imageRef: LIGHTWEIGHT_WORKBENCH_IMAGE });

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

// The one thing the golden path (review.spec.ts) structurally cannot cover:
// re-fetching a *live origin*. Its REE was acquired by upload, so it records a
// SWHID but no URL, and the strongest source verdict available there rests on
// the snapshot the bundle carries. Here the origin is real and gets fetched
// again, which is the only way the independent basis of this step is exercised.
// Cheap by comparison — no runtime is ever built.
test.describe("Review source", () => {
  test("source reproduction re-fetches the pinned origin and reports identical", async ({
    page,
  }) => {
    await startReeCreation(page);
    await provisionWorkbench(page, { imageRef: LIGHTWEIGHT_WORKBENCH_IMAGE });
    // Upload-acquired source has no origin to re-fetch, so a reviewable REE
    // needs the download path.
    await downloadSource(page, { url: E2E_GIT_ORIGIN_URL, sourceType: "git" });
    // The resolved commit is what the review re-fetches; wait for it to settle
    // onto the intent before reviewing, or the review races the metadata step.
    await expect(page.getByText(/Resolved to commit/)).toBeVisible({ timeout: 20000 });
    // Source identity is settled by the same backend operation. Waiting for the
    // actual value also proves a later editor autosave did not clobber it.
    await expect(
      page
        .getByRole("region", { name: "Workspace Snapshot" })
        .getByText(/^swh:1:dir:[0-9a-f]{40}$/),
    ).toBeVisible({ timeout: 20000 });

    const review = await openReviewConsole(page);
    // Nothing reproduced yet: source is the only runnable step, and its
    // evidence section says so rather than standing empty.
    await expect(review.getByText("Not reproduced yet.").first()).toBeVisible();
    await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeDisabled();

    expect(await reproduceSource(page)).toBe("IDENTICAL");

    // The verdict is on the step's own card in the strip. The attempt id it
    // belongs to is not surfaced anywhere — the console header that carried it
    // was removed with the floating HUD.
    await expect(
      review.getByRole("button", { name: /^Open Source review evidence, identical/ }),
    ).toBeVisible();
    // A settled source unlocks build and nothing beyond it: each later step
    // waits on the one before, so a certified runtime is still owed before
    // anything can be run inside it.
    await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeEnabled();
    await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeDisabled();
    await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeDisabled();
  });
});
