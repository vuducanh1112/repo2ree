import { expect, test } from "../helpers/fixtures";
import {
  openReviewConsole,
  provisionWorkbench,
  pythonHelloWorld,
  reproduceSource,
  selectReviewBasis,
  startReeCreation,
  uploadSource,
} from "../helpers/flow";

/**
 * Reviewing an REE that carries its own source.
 *
 * An uploaded source has no origin to re-fetch — the same shape an REE loaded
 * from a bundle has — and the origin-only review path had no answer for it at
 * all: the source step refused, and every later step gates on the source step.
 * Reproducing from the REE's own snapshot is what makes it reviewable, and the
 * console has to say plainly that the resulting verdict is an integrity check
 * rather than an independent reproduction.
 */
test.describe("Review from the REE's own artifacts", () => {
  test("an uploaded source is reviewable from the bundled snapshot", async ({ page }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    const review = await openReviewConsole(page);
    await selectReviewBasis(page, "From bundle");

    expect(await reproduceSource(page)).toBe("IDENTICAL");

    // The verdict is stated with what it is worth, not just what it is.
    await expect(review.getByText(/source verified from the REE's own artifacts/)).toBeVisible();
    await expect(review.getByText(/not an independent reproduction/)).toBeVisible();
    await expect(review.getByText(/review-[0-9a-f]+ · source identical/)).toBeVisible();
  });

  test("demanding an independent reproduction fails rather than quietly weakening", async ({
    page,
  }) => {
    await startReeCreation(page);
    await provisionWorkbench(page);
    await uploadSource(page, pythonHelloWorld());

    await openReviewConsole(page);
    await selectReviewBasis(page, "Independent");

    // There is no origin to fetch, and answering a weaker question than the one
    // asked would be worse than answering none.
    expect(await reproduceSource(page)).toBe("FAILED");
  });
});
