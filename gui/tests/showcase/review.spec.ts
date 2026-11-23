import { expect, test } from "../helpers/fixtures";
import {
  authoredRee,
  openReviewConsole,
  provisionFromBundle,
  reproduceActivation,
  reproduceBuild,
  reproduceExperiment,
  reproduceSource,
  selectReviewBasis,
  startReeCreation,
} from "../helpers/flow";

const EXPERIMENT = "python-hello";

test.describe("Review lifecycle", () => {
  test("reproduces another author's source, experiment environment, activation and result", async ({
    page,
  }) => {
    await test.step("seat someone else's REE on a fresh workbench", async () => {
      await startReeCreation(page);
      await provisionFromBundle(page, authoredRee());
    });

    const review = await openReviewConsole(page);

    await test.step("source: demanding an origin this REE never had fails", async () => {
      await expect(
        review.getByRole("button", { name: "Reproduce Build Experiment Environment" }),
      ).toBeDisabled();
      await selectReviewBasis(page, "Independent");

      expect(await reproduceSource(page)).toBe("FAILED");
    });

    await test.step("source: the REE's own snapshot reproduces its recorded identity", async () => {
      await selectReviewBasis(page, "From bundle");

      expect(await reproduceSource(page)).toBe("IDENTICAL");

      await expect(review.getByText(/^source verified from the REE's own artifacts/)).toBeVisible();
    });

    await test.step("build: the author's recipe rebuilds their experiment environment", async () => {
      await expect(
        review.getByRole("button", { name: "Reproduce Build Experiment Environment" }),
      ).toBeEnabled();
      await selectReviewBasis(page, "Strongest");

      expect(["IDENTICAL", "EQUIVALENT", "DIFFERENT"]).toContain(await reproduceBuild(page));

      await expect(review.getByText(/closure: \d+ matched · 0 missing · 0 extra/)).toBeVisible();
      await expect(review.getByText(/source and experiment environment verified/)).toHaveCount(0);
    });

    await test.step("activation: it enters the rebuilt experiment environment", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeEnabled();

      expect(await reproduceActivation(page)).toBe("COMPLETE");

      await expect(
        review.getByText("activation: it enters the experiment environment and hands over"),
      ).toBeVisible();
    });

    await test.step("experiments open only once the experiment environment is known to come up", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeEnabled();
      await expect(review.getByText("RESULTS · 0/1 REPRODUCED")).toBeVisible();
    });

    await test.step("experiments: the author's result holds in the reviewer's experiment environment", async () => {
      expect(["IDENTICAL", "REPRODUCED"]).toContain(await reproduceExperiment(page, EXPERIMENT));

      await expect(review.getByText("RESULTS · 1/1 REPRODUCED")).toBeVisible();
      await expect(review.getByText(/\.verify\.sh$/)).toBeVisible();
      await expect(
        review.getByRole("button", { name: `Reproduce experiment ${EXPERIMENT}` }),
      ).toHaveText("Re-run");
    });

    await test.step("the whole chain is stated with what each part is worth", async () => {
      await expect(
        review.getByRole("button", { name: /^Open Source review evidence, identical/ }),
      ).toBeVisible();
      await expect(
        review.getByRole("button", {
          name: /^Open Build Experiment Environment review evidence, (identical|equivalent|different)/,
        }),
      ).toBeVisible();
      await expect(
        review.getByRole("button", { name: /^Open Test Activation review evidence, complete/ }),
      ).toBeVisible();
      await expect(review.getByText(/^source verified from the REE's own artifacts/)).toBeVisible();
    });
  });
});
