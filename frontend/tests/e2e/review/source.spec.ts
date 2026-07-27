import { expect, test } from "../helpers/fixtures";
import {
  downloadSource,
  openReviewConsole,
  provisionWorkbench,
  reproduceSource,
  startReeCreation,
} from "../helpers/flow";

// The same origin the source-acquisition spec fetches. A review re-fetches the
// commit the author's acquisition resolved to (it is pinned onto the intent), so
// the comparison is deterministic even though HEAD moves.
const GIT_ORIGIN_URL = "https://github.com/vuducanh1112/repo2ree.git";

// The one thing the golden path (lifecycle.spec.ts) structurally cannot cover:
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
    await provisionWorkbench(page);
    // Upload-acquired source has no origin to re-fetch, so a reviewable REE
    // needs the download path.
    await downloadSource(page, { url: GIT_ORIGIN_URL, sourceType: "git" });
    // The resolved commit is what the review re-fetches; wait for it to settle
    // onto the intent before reviewing, or the review races the metadata step.
    await expect(page.getByText(/Resolved to commit/)).toBeVisible({ timeout: 20000 });

    const review = await openReviewConsole(page);
    await expect(review.getByText("ready for source review")).toBeVisible();
    await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeDisabled();

    expect(await reproduceSource(page)).toBe("IDENTICAL");

    // The attempt is persisted evidence, identified in the console header.
    await expect(review.getByText(/review-[0-9a-f]+ · source identical/)).toBeVisible();
    // A settled source unlocks build and nothing beyond it: each later step
    // waits on the one before, so a certified runtime is still owed before
    // anything can be run inside it.
    await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeEnabled();
    await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeDisabled();
    await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeDisabled();
  });
});
