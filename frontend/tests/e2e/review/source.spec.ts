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

// The source step of the review lifecycle: reproduce the author's acquisition in
// an isolated namespace and compare the identity that comes out. Build has its
// own spec (build.spec.ts); the siblings still without a reviewer path stay
// disabled, which this spec pins.
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
    // A settled source unlocks build — and nothing beyond it, since activation
    // and experiments have no reviewer path yet.
    await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeEnabled();
    await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeDisabled();
    await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeDisabled();
  });
});
