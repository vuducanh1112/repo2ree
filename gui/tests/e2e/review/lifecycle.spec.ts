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

// The experiment the bundled REE declares, and the criterion its author wrote.
const EXPERIMENT = "python-hello";

/**
 * The reviewer lifecycle end to end — source, build, activation, experiments —
 * against an REE this suite did not author.
 *
 * Starting from `examples/rees/ree-hello-world.zip` rather than authoring one
 * is the point, not a shortcut. A review is a claim about *someone else's*
 * evidence, and an REE the same spec just produced is the one baseline that
 * cannot demonstrate that: every digest it compares against was written moments
 * earlier by the same code path, in the same container, from the same inputs.
 * The bundle carries real author receipts emitted by the demo authoring flow,
 * so the comparisons are against persisted evidence from a separate run rather
 * than fixtures assembled by this review spec.
 *
 * It is also much less work. The whole authoring phase disappears: no upload,
 * no author-side build, no scan, no author-side activation or experiment run.
 * What remains is the review itself.
 *
 * Two bases in one attempt, neither of them a preference: the bundle's source
 * was upload-acquired so there is no origin to re-fetch (bundled), while its
 * runtime is deliberately omitted from this compact review fixture, so there
 * is nothing to certify but a real rebuild (independent). That combination is
 * not a special case — it is what every downloaded REE of this shape offers.
 *
 * Nothing in this REE is fully pinned — its Dockerfile floats
 * `python:3.11-slim`, and while it pins `pandas==2.2.1` it does not pin that
 * package's own dependencies — so the runtime may drift a package at a time as
 * upstream moves. That is precisely the situation the tool exists to detect:
 * build records any difference, activation asks whether the environment still
 * comes up, and the experiment asks whether the result still holds.
 */
test.describe("Review lifecycle", () => {
  test("reproduces another author's source, runtime, activation and result", async ({ page }) => {
    // One cold DinD rebuild of the author's runtime, a scan, and two container
    // runs — all on the reviewer's side. No authoring at all.
    test.setTimeout(20 * 60 * 1000);

    await test.step("seat someone else's REE on a fresh workbench", async () => {
      await startReeCreation(page);
      await provisionFromBundle(page, authoredRee());
    });

    // Switch the persistent status bar to Review once; every step below reads
    // from the same review panel beneath it.
    const review = await openReviewConsole(page);

    await test.step("source: demanding an origin this REE never had fails", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeDisabled();
      // The bundle's source was acquired by upload, so it records a SWHID but no
      // origin. Answering a weaker question than the one asked would be worse
      // than answering none, so the step refuses rather than quietly falling
      // back to the snapshot sitting right there.
      await selectReviewBasis(page, "Independent");

      expect(await reproduceSource(page)).toBe("FAILED");
    });

    await test.step("source: the REE's own snapshot reproduces its recorded identity", async () => {
      // Source always opens a fresh attempt, so this leaves the refusal above
      // behind rather than resuming it.
      await selectReviewBasis(page, "From bundle");

      expect(await reproduceSource(page)).toBe("IDENTICAL");

      await expect(review.getByText(/^source verified from the REE's own artifacts/)).toBeVisible();
    });

    await test.step("build: the author's recipe rebuilds their runtime", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Build" })).toBeEnabled();
      // Back to the default: the bundle ships no runtime artifact, so there is
      // nothing to certify except by running the author's build script over the
      // source this attempt just acquired. A genuine reproduction.
      await selectReviewBasis(page, "Strongest");

      // The tier is deliberately not pinned, and this is the interesting part
      // of the whole spec. The baseline's Dockerfile says `FROM python:3.11-slim`
      // — a floating tag — so the environment the author captured drifts away
      // from what the world now builds, one upstream package at a time. On the
      // day this was written the rebuild came back `different` over a single
      // version bump in 2842 packages, and that number only grows with the age
      // of the fixture. Asserting `equivalent` would be asserting that upstream
      // stands still.
      expect(["IDENTICAL", "EQUIVALENT", "DIFFERENT"]).toContain(await reproduceBuild(page));

      // What *is* stable, and what the verdict actually rests on: the same set
      // of packages got installed. Nothing appeared, nothing vanished — any
      // divergence is a version that moved, which is a statement about upstream
      // rather than about whether the recipe still describes this software.
      await expect(review.getByText(/closure: \d+ matched · 0 missing · 0 extra/)).toBeVisible();
      // The runtime was rebuilt, not unpacked — the notice would name it too.
      await expect(review.getByText(/source and runtime verified/)).toHaveCount(0);
    });

    await test.step("activation: the rebuilt runtime is inhabitable", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Test Activation" })).toBeEnabled();

      expect(await reproduceActivation(page)).toBe("COMPLETE");

      await expect(review.getByText("activation: the runtime is inhabitable")).toBeVisible();
    });

    await test.step("experiments open only once the runtime is known to come up", async () => {
      await expect(review.getByRole("button", { name: "Reproduce Experiments" })).toBeEnabled();
      await expect(review.getByText("RESULTS · 0/1 REPRODUCED")).toBeVisible();
    });

    await test.step("experiments: the author's result holds in the reviewer's runtime", async () => {
      // Both are passes, and which one this earns is a property of the
      // experiment rather than of the review: this one prints a fixed DataFrame,
      // so its result file comes out byte for byte the same and takes the
      // stronger `identical` tier. An experiment that stamped a timestamp would
      // land on `reproduced` with the same verify script — the distinction the
      // verdict ladder exists to draw, and the reason neither is asserted alone.
      //
      // It is also where the age of this baseline pays off: the author's receipt
      // predates `verify_exit_code`, so the claim has to be read out of its
      // status instead, or this would come back inconclusive.
      expect(["IDENTICAL", "REPRODUCED"]).toContain(await reproduceExperiment(page, EXPERIMENT));

      await expect(review.getByText("RESULTS · 1/1 REPRODUCED")).toBeVisible();
      // A pass is worth exactly as much as the script that granted it, so the
      // criterion is on screen rather than summarised away.
      await expect(review.getByText(/\.verify\.sh$/)).toBeVisible();
      // A settled experiment offers a re-run, not a first run.
      await expect(
        review.getByRole("button", { name: `Reproduce experiment ${EXPERIMENT}` }),
      ).toHaveText("Re-run");
    });

    await test.step("the whole chain is stated with what each part is worth", async () => {
      // Every step's verdict stands on its own card in the strip, so the chain
      // reads end to end without opening anything. (The attempt's own id is not
      // surfaced anywhere since the console header was removed; the drawer
      // below is what carries the detail now.)
      await expect(
        review.getByRole("button", { name: /^Open Source review evidence, identical/ }),
      ).toBeVisible();
      await expect(
        review.getByRole("button", {
          name: /^Open Build review evidence, (identical|equivalent|different)/,
        }),
      ).toBeVisible();
      await expect(
        review.getByRole("button", { name: /^Open Test Activation review evidence, complete/ }),
      ).toBeVisible();
      // The source rested on the REE's own bytes and says so; the rebuild did
      // not, and the notice must not claim otherwise for it.
      await expect(review.getByText(/^source verified from the REE's own artifacts/)).toBeVisible();
    });
  });
});
